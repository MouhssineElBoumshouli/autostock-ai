"""A big, made-up shop for speed checks only: 50,000 parts, 3 branches, 2 years of daily sales with
the same mix as the demo shop (a few parts sell every day, most rarely or never). It is marked
is_demo, kept apart from the demo shop (each one only ever replaces itself), and never shown in
the presentation. No true demand and no planted problems: it only has to be big and realistic.

Everything is written with PostgreSQL COPY, in batches of parts, so it takes minutes, not hours.

Run inside Docker:  docker compose exec api python -m app.demo.big_shop
"""

import io
import secrets
import uuid
from collections import Counter
from datetime import date, timedelta
from time import perf_counter

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password
from app.db import SessionLocal, utc_now
from app.demo.demo_shop import (
    BRANCHES,
    CAR_POPULARITY,
    CARS,
    FAMILIES,
    HISTORY_DAYS,
    PACK_SIZES,
    RAMADAN_FACTOR,
    STOCK_OUT_CHANCE,
    WEEKDAY_FACTORS,
    SellingStyle,
    branch_quantities,
    eid_factor,
    increasing_ids,
    make_suppliers,
    remove_demo_shop,
    season_factor,
    skip_reference_checks,
    stock_buckets,
    target_quantity,
)
from app.demo.production_guard import refuse_demo_in_production
from app.forecast.calendar import ramadan_flags
from app.models import Branch, Organization, SaleLine, SynonymGroup, User
from app.search.default_synonyms import DEFAULT_SYNONYMS

BIG_SHOP_NAME = "BIG TEST SHOP (made-up data, speed checks only)"
BIG_OWNER_EMAIL = "big@autostock.local"
PARTS = 50_000
# The demo catalog (about 2,000 parts) repeated for engine versions of each car, each with its own
# OEM number: 25 x 2,014 = 50,350, spread down to 50,000.
VERSIONS = [
    "1.2", "1.4", "1.5 dCi", "1.6", "1.6 HDi", "1.9 D", "2.0", "2.0 HDi", "2.2 dCi", "2.5 D",
    "Essence 2008-2012", "Essence 2013-2016", "Essence 2017-2020", "Essence 2021+",
    "Diesel 2008-2012", "Diesel 2013-2016", "Diesel 2017-2020", "Diesel 2021+",
    "Phase 1", "Phase 2", "Phase 3", "GPL", "Utilitaire", "Automatique", "Sport",
]  # fmt: skip
STOCK_HISTORY_DAYS = 120  # like the demo: stock day by day for the last 4 months
PARTS_PER_BATCH = 2_000


def create_big_shop(db: Session, last_day: date, parts_count: int = PARTS, seed: int = 8) -> tuple[Organization, Counter]:
    """Replaces any old big test shop with a new one whose sales end on `last_day`. Returns the
    shop and how many rows went into each table."""
    rng = np.random.default_rng(seed)
    skip_reference_checks(db)
    remove_demo_shop(db, BIG_SHOP_NAME)
    shop = Organization(name=BIG_SHOP_NAME, currency="MAD", is_demo=True)
    db.add(shop)
    db.flush()
    db.add_all(SynonymGroup(organization_id=shop.id, words=words) for words in DEFAULT_SYNONYMS)
    branches = [Branch(organization_id=shop.id, name=name) for name in BRANCHES]
    suppliers = make_suppliers(shop.id)
    db.add_all([*branches, *suppliers])
    db.flush()

    catalog = _catalog(rng, parts_count)
    branch_ids = [b.id for b in branches]
    branch_factors = np.array(list(BRANCHES.values()))
    supplier_ids = [s.id for s in suppliers]
    first_day = last_day - timedelta(days=HISTORY_DAYS - 1)
    calendar = _calendar(first_day)
    buckets = stock_buckets(rng, len(catalog))
    counts = Counter()
    writer = _Writer(db, shop.id)

    for start in range(0, len(catalog), PARTS_PER_BATCH):
        batch = catalog[start : start + PARTS_PER_BATCH]
        part_ids = increasing_ids(len(batch))
        styles = [item[3] for item in batch]
        popularity = np.array([item[5] for item in batch])
        wanted = _daily_demand(rng, calendar, styles, branch_factors, popularity)  # (parts, branches, days)
        sold, outs = _with_stock_outs(rng, wanted)

        rates = wanted.mean(axis=2)  # (parts, branches)
        part_rows, stock_rows = [], []
        for i, (name, category, brand, _style, price, _popularity, oem, sku, pack) in enumerate(batch):
            min_days = rng.uniform(8, 12) if buckets[start + i] == "running_out" else rng.uniform(10, 18)
            min_stock = max(1, round(rates[i].sum() * min_days))
            total = target_quantity(rng, buckets[start + i], min_stock, rates[i].sum(), min_days)
            for b, quantity in enumerate(branch_quantities(rng, total, rates[i])):
                stock_rows.append((part_ids[i], branch_ids[b], quantity))
            supplier = supplier_ids[rng.integers(0, len(supplier_ids))]
            part_rows.append((sku, name, brand, category, oem, price * 70, price * 100, min_stock, pack, supplier, True))
            counts[buckets[start + i]] += 1

        writer.copy("parts", PART_COLUMNS, part_rows, part_ids)
        writer.copy("stock_levels", ["part_id", "branch_id", "quantity"], stock_rows)
        writer.sales(part_ids, branch_ids, [item[4] * 100 for item in batch], sold, first_day)
        writer.copy("stock_outs", ["part_id", "branch_id", "first_day", "last_day"],
                    [(part_ids[p], branch_ids[b], first_day + timedelta(days=f), first_day + timedelta(days=l)) for p, b, f, l in outs])
        quantities = np.array([q for _, _, q in stock_rows]).reshape(len(batch), len(branch_ids))
        writer.stock_history(part_ids, branch_ids, sold, outs, quantities, first_day)
        print(f"  {start + len(batch):,} of {len(catalog):,} parts written", flush=True)

    counts.update(writer.rows)
    return shop, counts


PART_COLUMNS = ["sku", "name", "brand", "category", "oem_reference", "unit_cost", "sale_price", "min_stock", "pack_size", "supplier_id", "is_active"]


def _catalog(rng: np.random.Generator, parts_count: int) -> list[tuple]:
    """(name, category, brand, style, price, popularity, oem, sku, pack size) for each part. Like
    the demo: brands of one (family, car, version) share an OEM number, so they are equivalents,
    and a car's popularity sets how much its parts sell, with dead stock on unpopular cars."""
    catalog = []
    for version in VERSIONS:
        for name, category, brands, style, price in FAMILIES:
            for car in CARS:
                oem = f"{rng.integers(1000, 9999)} {rng.integers(100, 999)} {rng.integers(100, 999)}"
                popularity = CAR_POPULARITY[car]
                for brand in brands:
                    dead = rng.random() < max(0.0, 0.5 - popularity)
                    catalog.append((f"{name} - {car} {version}", category, brand, style, price, 0.0 if dead else popularity, oem))
    catalog = [catalog[i * len(catalog) // parts_count] for i in range(parts_count)] if parts_count < len(catalog) else catalog
    return [(*item, f"BIG-{n + 1:05d}", PACK_SIZES.get(item[0].split(" - ")[0], 1)) for n, item in enumerate(catalog)]


def _calendar(first_day: date) -> dict:
    """Everything about the days that is the same for every part: weekday, Ramadan, Eid, and the
    season for each selling style."""
    dates = [first_day + timedelta(days=i) for i in range(HISTORY_DAYS)]
    shared = (
        WEEKDAY_FACTORS[[d.weekday() for d in dates]]
        * np.where(ramadan_flags(first_day, HISTORY_DAYS) > 0, RAMADAN_FACTOR, 1.0)
        * eid_factor(first_day.toordinal() + np.arange(HISTORY_DAYS))
    )
    days_of_year = np.array([d.timetuple().tm_yday for d in dates])
    return {"shared": shared, "days_of_year": days_of_year, "seasons": {}}


def _daily_demand(rng: np.random.Generator, calendar: dict, styles: list[SellingStyle], branch_factors: np.ndarray,
                  popularity: np.ndarray) -> np.ndarray:
    """Pieces customers wanted each day, the demo's recipe (customers + extra pieces), for a whole
    batch at once: one array (parts, branches, days)."""
    parts, branches = len(styles), len(branch_factors)
    seasons = calendar["seasons"]
    for style in set(styles):
        if style not in seasons:
            seasons[style] = season_factor(calendar["days_of_year"], style) * calendar["shared"]
    days = np.arange(HISTORY_DAYS)
    low = np.array([s.customers_per_day[0] for s in styles])[:, None]
    high = np.array([s.customers_per_day[1] for s in styles])[:, None]
    base = rng.uniform(low, high, (parts, branches)) * branch_factors * popularity[:, None]
    trend = 1.0 + rng.uniform(-0.1, 0.2, (parts, branches))[:, :, None] * days / 365
    season = np.stack([seasons[s] for s in styles])[:, None, :]
    customers = rng.poisson(base[:, :, None] * season * trend)
    batches = rng.gamma(0.5, 2.0, customers.shape)
    extra = np.array([s.extra_pieces for s in styles])[:, None, None]
    return customers + rng.poisson(extra * customers * batches)


def _with_stock_outs(rng: np.random.Generator, wanted: np.ndarray) -> tuple[np.ndarray, list[tuple[int, int, int, int]]]:
    """Sales (0 on empty-shelf days) and the empty-shelf periods (part, branch, first, last day)."""
    sold = wanted.copy()
    outs = []
    parts, branches, days = wanted.shape
    for p, b in zip(*np.nonzero(rng.random((parts, branches)) < STOCK_OUT_CHANCE)):
        for _ in range(rng.integers(1, 3)):
            first = int(rng.integers(0, days - 5))
            last = min(first + int(rng.integers(4, 22)), days - 1)
            sold[p, b, first : last + 1] = 0
            outs.append((int(p), int(b), first, last))
    return sold, outs


class _Writer:
    """Writes rows with COPY inside the session's transaction (one id and created_at per row)."""

    def __init__(self, db: Session, organization_id: uuid.UUID):
        self.cursor = db.connection().connection.dbapi_connection.cursor()
        self.prefix = f"{utc_now().isoformat()}\t{organization_id}\t"
        self.rows = Counter()

    def copy(self, table: str, columns: list[str], rows: list[tuple], ids: list[uuid.UUID] | None = None) -> None:
        ids = ids or increasing_ids(len(rows))
        text = "".join(f"{id_}\t{self.prefix}" + "\t".join(map(str, row)) + "\n" for id_, row in zip(ids, rows))
        self._send(table, columns, text, len(rows))

    def sales(self, part_ids: list, branch_ids: list, prices: list[int], sold: np.ndarray, first_day: date) -> None:
        """One sale line per part, branch and day with a sale."""
        days = [(first_day + timedelta(days=d)).isoformat() for d in range(sold.shape[2])]
        keys = [[f"{part}\t{branch}\t" for branch in branch_ids] for part in part_ids]
        p, b, d = np.nonzero(sold)
        quantity = sold[p, b, d]
        text = "".join(
            f"{row_id}\t{self.prefix}{keys[i][j]}{days[k]}\t{q}\t{prices[i]}\n"
            for row_id, i, j, k, q in zip(increasing_ids(len(p)), p.tolist(), b.tolist(), d.tolist(), quantity.tolist())
        )
        self._send("sale_lines", ["part_id", "branch_id", "sold_on", "quantity", "unit_price"], text, len(p))

    def stock_history(self, part_ids: list, branch_ids: list, sold: np.ndarray, outs: list, quantities: np.ndarray, first_day: date) -> None:
        """Stock at the end of each of the last STOCK_HISTORY_DAYS days, worked back from today's
        stock (yesterday = today + what sold today), with a delivery whenever that would pass a full
        shelf; 0 on empty-shelf days. One row on the first day and on every day it changed."""
        recent = sold[:, :, -STOCK_HISTORY_DAYS:]
        sold_after = np.cumsum(recent[:, :, ::-1], axis=2)[:, :, ::-1] - recent  # sold after the end of each day
        daily = np.maximum(recent.mean(axis=2), 0.05)
        full = np.maximum(np.maximum(quantities, np.round(daily * 45)), 3)[:, :, None]
        stock = np.where(quantities[:, :, None] + sold_after > full, (quantities[:, :, None] + sold_after - 1) % full + 1,
                         quantities[:, :, None] + sold_after)
        start = sold.shape[2] - STOCK_HISTORY_DAYS
        for p, b, first, last in outs:
            stock[p, b, max(first - start, 0) : max(last - start + 1, 0)] = 0
        stock = stock.astype(int)
        changed = np.ones(stock.shape, dtype=bool)
        changed[:, :, 1:] = stock[:, :, 1:] != stock[:, :, :-1]
        rows = [
            (part_ids[p], branch_ids[b], first_day + timedelta(days=start + d), stock[p, b, d])
            for p, b, d in zip(*(axis.tolist() for axis in np.nonzero(changed)))
        ]
        self.copy("stock_history", ["part_id", "branch_id", "day", "quantity"], rows)

    def _send(self, table: str, columns: list[str], text: str, count: int) -> None:
        names = ", ".join(["id", "created_at", "organization_id", *columns])
        with self.cursor.copy(f"COPY {table} ({names}) FROM STDIN") as copy:
            copy.write(text.encode())
        self.rows[table] += count


def add_big_owner(db: Session, shop: Organization) -> str:
    """An owner account for the big test shop, with a new random password each time."""
    if not shop.is_demo:
        raise ValueError("Test accounts are only for demo shops.")
    password = secrets.token_urlsafe(9)
    db.add(User(organization_id=shop.id, name="Big Shop Owner", email=BIG_OWNER_EMAIL, password_hash=hash_password(password), role="owner"))
    return password


def main() -> None:
    refuse_demo_in_production()
    started = perf_counter()
    with SessionLocal() as db:
        shop, counts = create_big_shop(db, last_day=date.today() - timedelta(days=1))
        password = add_big_owner(db, shop)
        db.commit()
        lines = db.scalar(select(func.count()).select_from(SaleLine).where(SaleLine.organization_id == shop.id))
    print(f"Created '{BIG_SHOP_NAME}': {counts['parts']:,} parts, {lines:,} sales lines, "
          f"{counts['stock_history']:,} stock history rows, in {perf_counter() - started:.0f} s.")
    print(f"Log in with  email: {BIG_OWNER_EMAIL}  password: {password}")


if __name__ == "__main__":
    main()
