"""A clearly labeled, made-up demo shop: about 200 parts, 3 branches, 18 months of daily sales.

It also saves the true demand it was made from (including stock-out days and 60 days after the
history ends), so forecasts can be checked against the truth, and problems planted on purpose with
their true dates (planted_problems.py), so alerts can be checked too. It always creates its own
organization marked is_demo and never touches a real shop.

Run inside Docker:  docker compose exec api python -m app.demo.demo_shop
"""

import secrets
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password
from app.db import Base, SessionLocal, utc_now
from app.demo.planted_problems import DemoSeries, plant_problems, planted_rows, stock_history_rows
from app.demo.production_guard import refuse_demo_in_production
from app.forecast.calendar import ramadan_flags
from app.models import Branch, DemoPlantedProblem, Organization, Part, SaleLine, Supplier, SynonymGroup, User
from app.search.default_synonyms import DEFAULT_SYNONYMS

DEMO_SHOP_NAME = "DEMO SHOP (made-up data)"
DEMO_OWNER_EMAIL = "demo@autostock.local"
HISTORY_DAYS = 548  # 18 months
FUTURE_DAYS = 60  # true demand kept after the history ends, to check forecasts
BRANCHES = {"Casablanca - Maarif": 1.0, "Rabat - Agdal": 0.7, "Marrakech - Gueliz": 0.5}
# Monday..Sunday. Friday prayer shortens the day; most shops are closed on Sunday.
WEEKDAY_FACTORS = np.array([1.0, 1.0, 1.0, 1.0, 0.8, 1.05, 0.35])
RAMADAN_FACTOR = 0.7
STOCK_OUT_CHANCE = 0.35
# Made-up Moroccan distributors, each with its own delivery time (Step 5 will need it).
SUPPLIERS = [
    ("Atlas Distribution Pieces", "+212 522-301145", "contact@atlas-distribution.ma", 6),
    ("CasaPieces Auto", "+212 522-884421", "ventes@casapieces.ma", 3),
    ("Maghreb Auto Supply", "+212 537-662290", "commandes@maghrebautosupply.ma", 11),
    ("Rabat Pieces Express", "+212 537-119983", "info@rabatpieces.ma", 4),
    ("Groupe Alami Automobile", "+212 524-557712", "contact@groupe-alami.ma", 18),
    ("Tanger Auto Parts", "+212 539-443367", "info@tangerautoparts.ma", 21),
]
# How current stock is spread on the day the demo is created, as a share of all parts.
# "running_out" parts are above their minimum (so they still read as "Healthy") but have little
# cover left at their own selling rate — exactly what the forecast is meant to catch.
STOCK_BUCKETS = [("out", 0.04), ("low", 0.10), ("running_out", 0.08), ("healthy", 0.78)]
# Families the suppliers sell by the box; everything else comes one at a time.
PACK_SIZES = {"Oil filter": 5, "Engine oil 5W30 5L": 4, "Coolant 5L": 6, "Headlight bulb H7": 10, "Wiper blades (pair)": 5}
CARS = [
    "Dacia Logan 1.5 dCi", "Dacia Sandero 1.0", "Renault Clio 4 1.5 dCi", "Peugeot 208 1.6 HDi",
    "Peugeot 301 1.6", "Hyundai i10 1.1", "Fiat Uno 1.4", "VW Golf 7 2.0 TDI", "Toyota Corolla 1.6",
    "Kia Picanto 1.0", "Citroen C-Elysee 1.6 HDi", "Ford Fiesta 1.4",
]


@dataclass(frozen=True)
class SellingStyle:
    customers_per_day: tuple[float, float]  # range, in the main branch, before seasons
    extra_pieces: float  # average extra pieces per customer (garages buying several)
    summer_boost: float  # +80% at the July peak = 0.8
    winter_boost: float  # same, at the January peak


STEADY = SellingStyle((1.5, 5.0), 0.3, 0.0, 0.0)
ERRATIC = SellingStyle((0.5, 1.8), 2.0, 0.0, 0.0)
SLOW = SellingStyle((0.03, 0.2), 0.0, 0.0, 0.0)
LUMPY = SellingStyle((0.03, 0.15), 1.5, 0.0, 0.0)
SUMMER = SellingStyle((0.4, 1.5), 0.2, 1.2, 0.0)
WINTER = SellingStyle((0.4, 1.5), 0.2, 0.0, 1.2)
BATTERY = SellingStyle((0.3, 1.0), 0.0, 0.8, 0.8)

# (part name, category, brands, selling style, how many parts, price in MAD)
FAMILIES = [
    ("Oil filter", "Filters", ["Purflux", "Mann", "Bosch"], STEADY, 12, 60),
    ("Air filter", "Filters", ["Mann", "Purflux"], STEADY, 10, 90),
    ("Engine oil 5W30 5L", "Oils", ["Total", "Castrol", "Motul"], STEADY, 8, 380),
    ("Cabin filter", "Filters", ["Bosch", "Valeo"], STEADY, 6, 110),
    ("Spark plugs (set of 4)", "Ignition", ["NGK", "Bosch"], STEADY, 6, 160),
    ("Brake pads front", "Brakes", ["TRW", "Bosch", "Ferodo"], ERRATIC, 14, 320),
    ("Brake discs front (pair)", "Brakes", ["TRW", "Brembo"], ERRATIC, 10, 650),
    ("Headlight bulb H7", "Lighting", ["Philips", "Osram"], ERRATIC, 8, 70),
    ("Shock absorber front", "Suspension", ["Monroe", "Sachs"], LUMPY, 12, 700),
    ("Timing belt kit", "Engine", ["Gates", "Dayco"], LUMPY, 10, 900),
    ("Clutch kit", "Transmission", ["Valeo", "Luk", "Sachs"], SLOW, 14, 1800),
    ("Alternator", "Electrical", ["Valeo", "Bosch"], SLOW, 12, 2400),
    ("Starter motor", "Electrical", ["Valeo", "Bosch"], SLOW, 10, 1900),
    ("Water pump", "Cooling", ["SKF", "Dayco"], SLOW, 10, 550),
    ("Radiator", "Cooling", ["Valeo", "Nissens"], SUMMER, 8, 1300),
    ("Coolant 5L", "Cooling", ["Total", "Motul"], SUMMER, 8, 140),
    ("AC compressor", "Air conditioning", ["Valeo", "Denso"], SUMMER, 6, 3500),
    ("Cooling fan", "Cooling", ["Valeo", "Nissens"], SUMMER, 6, 900),
    ("Wiper blades (pair)", "Visibility", ["Bosch", "Valeo"], WINTER, 12, 150),
    ("Glow plugs (set of 4)", "Ignition", ["Bosch", "NGK"], WINTER, 6, 420),
    ("Battery 70Ah", "Electrical", ["Varta", "Bosch"], BATTERY, 10, 1100),
]


@dataclass
class DemoPart:
    part: Part
    style: SellingStyle


def season_factor(days_of_year: np.ndarray, style: SellingStyle) -> np.ndarray:
    """Smooth bumps around 15 July (summer) and 15 January (winter)."""

    def bump(peak_day: int) -> np.ndarray:
        distance = np.abs(days_of_year - peak_day)
        distance = np.minimum(distance, 365 - distance)
        return np.exp(-((distance / 40.0) ** 2))

    return 1.0 + style.summer_boost * bump(196) + style.winter_boost * bump(15)


def true_demand(rng: np.random.Generator, first_day: date, days: int, style: SellingStyle, branch_factor: float) -> np.ndarray:
    """Pieces customers wanted on each day: customers (Poisson) plus extra pieces they bought."""
    dates = [first_day + timedelta(days=i) for i in range(days)]
    weekdays = WEEKDAY_FACTORS[[d.weekday() for d in dates]]
    seasons = season_factor(np.array([d.timetuple().tm_yday for d in dates]), style)
    ramadan = np.where(ramadan_flags(first_day, days) > 0, RAMADAN_FACTOR, 1.0)
    trend = 1.0 + rng.uniform(-0.1, 0.2) * np.arange(days) / 365  # -10% to +20% a year
    base = rng.uniform(*style.customers_per_day) * branch_factor
    customers = rng.poisson(base * weekdays * seasons * ramadan * trend)
    # Extra pieces come unevenly: most days none, some days a garage buys a whole batch.
    batches = rng.gamma(0.5, 2.0, days)  # average 1, often near 0, sometimes 3 or more
    return customers + rng.poisson(style.extra_pieces * customers * batches)


def stock_out_periods(rng: np.random.Generator, history_days: int) -> list[tuple[int, int]]:
    """0 to 2 periods (first and last day index, inside the history) when the shelf was empty."""
    if rng.random() > STOCK_OUT_CHANCE:
        return []
    periods = []
    for _ in range(rng.integers(1, 3)):
        first = int(rng.integers(0, history_days - 5))
        periods.append((first, min(first + int(rng.integers(4, 22)), history_days - 1)))
    return periods


def remove_demo_shops(db: Session) -> None:
    """Deletes every demo shop and all its rows. Real shops (is_demo false) are never touched."""
    demo_ids = db.scalars(select(Organization.id).where(Organization.is_demo)).all()
    if not demo_ids:
        return
    for table in reversed(Base.metadata.sorted_tables):
        if "organization_id" in table.c:
            db.execute(delete(table).where(table.c.organization_id.in_(demo_ids)))
    db.execute(delete(Organization).where(Organization.id.in_(demo_ids)))


def create_demo_shop(
    db: Session, last_day: date, parts_count: int | None = None, history_days: int = HISTORY_DAYS, seed: int = 7
) -> tuple[Organization, Counter]:
    """Replaces any old demo shop with a new one whose sales history ends on `last_day`.
    Returns the shop and how many parts started out of stock, low, running out soon, or healthy."""
    rng = np.random.default_rng(seed)
    remove_demo_shops(db)
    shop = Organization(name=DEMO_SHOP_NAME, currency="MAD", is_demo=True)
    db.add(shop)
    db.flush()
    # The same starting synonym list every real shop gets at setup (app/api/setup.py).
    db.add_all(SynonymGroup(organization_id=shop.id, words=words) for words in DEFAULT_SYNONYMS)
    branches = {Branch(organization_id=shop.id, name=name): factor for name, factor in BRANCHES.items()}
    db.add_all(branches)
    suppliers = _make_suppliers(shop.id)
    db.add_all(suppliers)
    db.flush()
    parts = _make_parts(shop.id, parts_count, rng, suppliers)
    db.add_all(item.part for item in parts)
    db.flush()
    buckets = _stock_buckets(rng, len(parts))

    first_day = last_day - timedelta(days=history_days - 1)
    series, outs = [], []
    counts = Counter()
    for item, bucket in zip(parts, buckets):
        group = []
        for branch, factor in branches.items():
            wanted = true_demand(rng, first_day, history_days + FUTURE_DAYS, item.style, factor)
            sold = wanted[:history_days].copy()
            out_days = np.zeros(history_days, dtype=bool)
            for first, last in stock_out_periods(rng, history_days):
                sold[first : last + 1] = 0
                out_days[first : last + 1] = True
                outs.append((item.part.id, branch.id, first_day + timedelta(days=first), first_day + timedelta(days=last)))
            group.append(DemoSeries(item.part, branch.id, sold, wanted, out_days))

        branch_rates = np.array([s.wanted[:history_days].mean() for s in group])
        daily_rate = branch_rates.sum()
        min_days = rng.uniform(8, 12) if bucket == "running_out" else rng.uniform(10, 18)  # "about 2 weeks"
        item.part.min_stock = max(1, round(daily_rate * min_days))
        total = _target_quantity(rng, bucket, item.part.min_stock, daily_rate, min_days)
        for s, quantity in zip(group, _branch_quantities(rng, total, branch_rates)):
            s.quantity = quantity
        series += group
        counts[bucket] += 1

    planted = plant_problems(rng, series)
    history = [row for s in series for row in stock_history_rows(rng, s, first_day)]
    sales, truth, stock = [], [], []
    for s in series:
        key = (s.part.id, s.branch_id)
        sales += [(*key, first_day + timedelta(days=int(i)), int(s.sold[i]), s.part.sale_price) for i in np.flatnonzero(s.sold)]
        truth += [(*key, first_day + timedelta(days=int(i)), int(s.wanted[i])) for i in np.flatnonzero(s.wanted)]
        stock.append((*key, s.quantity))

    _copy(db, "sale_lines", ["part_id", "branch_id", "sold_on", "quantity", "unit_price"], shop.id, sales)
    _copy(db, "demo_true_demand", ["part_id", "branch_id", "day", "quantity"], shop.id, truth)
    _copy(db, "stock_outs", ["part_id", "branch_id", "first_day", "last_day"], shop.id, outs)
    _copy(db, "stock_levels", ["part_id", "branch_id", "quantity"], shop.id, stock)
    _copy(db, "stock_history", ["part_id", "branch_id", "day", "quantity"], shop.id, history)
    db.add_all(
        DemoPlantedProblem(organization_id=shop.id, part_id=part, branch_id=branch, kind=kind, first_day=first, last_day=last, details=details)
        for part, branch, kind, first, last, details in (planted_rows(s, first_day) for s in planted)
    )
    return shop, counts


def _target_quantity(rng: np.random.Generator, bucket: str, min_stock: int, daily_rate: float, min_days: float) -> int:
    """How many pieces the part starts with in total, to land in its assigned bucket."""
    if bucket == "out":
        return 0
    if bucket == "low":
        return max(1, round(min_stock * rng.uniform(0.3, 1.0)))
    if bucket == "running_out":  # above the minimum (reads "Healthy"), but little cover left
        cover_days = rng.uniform(min_days + 1, 14)
        return max(min_stock + 1, round(daily_rate * cover_days))
    cover_days = rng.uniform(25, 90)  # healthy: plenty of cover
    return max(min_stock + 1, round(daily_rate * cover_days))


def add_demo_owner(db: Session, shop: Organization) -> str:
    """An owner account to log in to the demo shop. Returns its password, new and random each time
    (so none is ever written in the code). Refuses any shop that is not a demo shop."""
    if not shop.is_demo:
        raise ValueError("Demo accounts are only for demo shops.")
    taken = db.scalar(select(User).where(User.email == DEMO_OWNER_EMAIL, User.organization_id != shop.id))
    if taken is not None:
        raise ValueError(f"{DEMO_OWNER_EMAIL} already belongs to a real shop.")
    password = secrets.token_urlsafe(9)
    db.add(User(organization_id=shop.id, name="Demo Owner", email=DEMO_OWNER_EMAIL, password_hash=hash_password(password), role="owner"))
    return password


def _make_suppliers(organization_id: uuid.UUID) -> list[Supplier]:
    return [
        Supplier(organization_id=organization_id, name=name, phone=phone, email=email, delivery_days=days)
        for name, phone, email, days in SUPPLIERS
    ]


def _make_parts(organization_id: uuid.UUID, parts_count: int | None, rng: np.random.Generator, suppliers: list[Supplier]) -> list[DemoPart]:
    parts = []
    for name, category, brands, style, count, price in FAMILIES:
        for i in range(count):
            supplier = suppliers[rng.integers(0, len(suppliers))]
            part = Part(
                organization_id=organization_id,
                sku=f"DEMO-{len(parts) + 1:04d}",
                name=f"{name} - {CARS[i % len(CARS)]}",
                brand=brands[i % len(brands)],
                category=category,
                unit_cost=price * 70,  # centimes: cost is 70% of the sale price
                pack_size=PACK_SIZES.get(name, 1),
                sale_price=price * 100,
                supplier_id=supplier.id,
            )
            parts.append(DemoPart(part, style))
    if parts_count is None or parts_count >= len(parts):
        return parts
    return [parts[i * len(parts) // parts_count] for i in range(parts_count)]  # spread over all families


def _stock_buckets(rng: np.random.Generator, n: int) -> list[str]:
    """One bucket per part ("out", "low", "running_out" or "healthy"), shuffled, in the shares of
    STOCK_BUCKETS (rounding goes to "healthy", the largest and least sensitive share)."""
    counts = {name: round(n * share) for name, share in STOCK_BUCKETS}
    counts["healthy"] += n - sum(counts.values())
    buckets = [name for name, count in counts.items() for _ in range(count)]
    rng.shuffle(buckets)
    return buckets


def _branch_quantities(rng: np.random.Generator, total: int, weights: np.ndarray) -> list[int]:
    """Splits `total` whole pieces across branches, busier branches getting more."""
    if total <= 0:
        return [0] * len(weights)
    share = weights / weights.sum() if weights.sum() > 0 else np.full(len(weights), 1 / len(weights))
    return [int(n) for n in rng.multinomial(total, share)]


def _copy(db: Session, table: str, columns: list[str], organization_id: uuid.UUID, rows: list[tuple]) -> None:
    """Fast bulk insert with PostgreSQL COPY, inside the same transaction as the session."""
    now = utc_now()
    cursor = db.connection().connection.dbapi_connection.cursor()
    names = ", ".join(["id", "created_at", "organization_id", *columns])
    with cursor.copy(f"COPY {table} ({names}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row((uuid.uuid4(), now, organization_id, *row))


def main() -> None:
    refuse_demo_in_production()
    with SessionLocal() as db:
        shop, counts = create_demo_shop(db, last_day=date.today() - timedelta(days=1))
        password = add_demo_owner(db, shop)
        db.commit()
        lines = db.scalar(select(func.count()).select_from(SaleLine).where(SaleLine.organization_id == shop.id))
        print(f"Created '{DEMO_SHOP_NAME}' with {len(FAMILIES)} part families and {lines} sales lines.")
        print(
            f"Stock on day 1: {counts['out']} out of stock, {counts['low']} low, "
            f"{counts['running_out']} running out within 14 days, {counts['healthy']} healthy."
        )
        planted = db.scalar(select(func.count()).select_from(DemoPlantedProblem).where(DemoPlantedProblem.organization_id == shop.id))
        print(f"Planted {planted} known problems (spikes, drops, stock that doesn't match sales) to test the alerts.")
        print(f"Log in to the demo shop with  email: {DEMO_OWNER_EMAIL}  password: {password}")
        print("(A new password is made each time the demo shop is created.)")


if __name__ == "__main__":
    main()
