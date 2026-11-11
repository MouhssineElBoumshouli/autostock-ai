"""A clearly labeled, made-up demo shop: about 2,000 parts named the way a Moroccan counter would
write them, real part brands, the cars common in Morocco, 3 branches, 24 months of daily sales.

It also saves the true demand it was made from (including stock-out days and 60 days after the
history ends), so forecasts can be checked against the truth, and problems planted on purpose with
their true dates (planted_problems.py), so alerts can be checked too. It always creates its own
organization marked is_demo and never touches a real shop.

Run inside Docker:  docker compose exec api python -m app.demo.demo_shop
"""

import random
import secrets
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from time import perf_counter

import numpy as np
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password
from app.db import Base, SessionLocal, utc_now
from app.demo.planted_problems import DemoSeries, plant_problems, planted_rows, stock_history_rows
from app.demo.production_guard import refuse_demo_in_production
from app.forecast.calendar import RAMADAN_FIRST_DAYS, ramadan_flags
from app.models import Branch, DemoPlantedProblem, Organization, Part, SaleLine, Supplier, SynonymGroup, User
from app.search.default_synonyms import DEFAULT_SYNONYMS

DEMO_SHOP_NAME = "DEMO SHOP (made-up data)"
DEMO_OWNER_EMAIL = "demo@autostock.local"
HISTORY_DAYS = 730  # 24 months
FUTURE_DAYS = 60  # true demand kept after the history ends, to check forecasts
BRANCHES = {"Casablanca - Maarif": 1.0, "Rabat - Agdal": 0.7, "Marrakech - Gueliz": 0.5}
# Monday..Sunday. Friday prayer shortens the day; most shops are closed on Sunday.
WEEKDAY_FACTORS = np.array([1.0, 1.0, 1.0, 1.0, 0.8, 1.05, 0.35])
RAMADAN_FACTOR = 0.7
# Eid al-Fitr is the day after Ramadan; Eid al-Adha is about 10 weeks later. Both move every year
# with the moon, so (unlike summer/winter) they are picked by date, not by day of the year.
EID_AL_FITR_DAYS = [first + timedelta(days=30) for first in RAMADAN_FIRST_DAYS]
EID_AL_ADHA_DAYS = [fitr + timedelta(days=70) for fitr in EID_AL_FITR_DAYS]
STOCK_OUT_CHANCE = 0.35
# Fictional Moroccan suppliers. Local ones drop off in a few days; importers hold stock abroad and
# take weeks (Step 5's order math needs both kinds).
SUPPLIERS = [
    ("CasaPieces Auto", "+212 522-884421", "ventes@casapieces.ma", 2),
    ("Rabat Pieces Express", "+212 537-119983", "info@rabatpieces.ma", 1),
    ("Marrakech Auto Direct", "+212 524-301187", "contact@marrakechautodirect.ma", 3),
    ("Atlas Distribution Pieces", "+212 522-301145", "contact@atlas-distribution.ma", 18),
    ("Maghreb Auto Supply", "+212 537-662290", "commandes@maghrebautosupply.ma", 28),
    ("Groupe Alami Automobile", "+212 528-557712", "contact@groupe-alami.ma", 35),
    ("Tanger Auto Parts", "+212 539-443367", "info@tangerautoparts.ma", 42),
    ("Souss Import Pieces", "+212 528-220156", "ventes@soussimportpieces.ma", 22),
]
# How current stock is spread on the day the demo is created, as a share of all parts.
# "running_out" parts are above their minimum (so they still read as "Healthy") but have little
# cover left at their own selling rate — exactly what the forecast is meant to catch.
STOCK_BUCKETS = [("out", 0.04), ("low", 0.10), ("running_out", 0.08), ("healthy", 0.78)]
# Families the suppliers sell by the box; everything else comes one at a time.
PACK_SIZES = {
    "Filtre à huile": 5,
    "Huile moteur 5W30 5L": 4,
    "Huile moteur 10W40 5L": 4,
    "Liquide de refroidissement 5L": 6,
    "Ampoule de phare H7": 10,
    "Ampoule de phare H4": 10,
    "Balai d'essuie-glace avant (paire)": 5,
}
# The cars common on Moroccan roads, most common first-ish. A part's popularity below follows its
# car: a Dacia Logan oil filter sells constantly, a Mercedes 190 one almost never — this is what
# makes the long tail (most parts barely move) without inventing a separate "rare part" flag.
CARS = [
    "Dacia Logan", "Dacia Sandero", "Dacia Duster", "Renault Clio", "Renault Kangoo",
    "Peugeot 208", "Peugeot 301", "Peugeot Partner", "Citroën Berlingo", "Citroën C-Elysée",
    "Hyundai Accent", "Hyundai i10", "Kia Picanto", "VW Golf", "Toyota Hilux",
    "Mercedes Sprinter", "Fiat Uno", "Fiat Palio", "Mercedes 190",
]
CAR_POPULARITY = {
    "Dacia Logan": 1.00, "Dacia Sandero": 0.85, "Renault Clio": 0.75, "Peugeot 208": 0.70,
    "Citroën C-Elysée": 0.65, "Dacia Duster": 0.55, "Peugeot Partner": 0.50, "Renault Kangoo": 0.45,
    "Citroën Berlingo": 0.45, "Hyundai Accent": 0.40, "Hyundai i10": 0.38, "Kia Picanto": 0.35,
    "Mercedes Sprinter": 0.30, "Toyota Hilux": 0.28, "Peugeot 301": 0.25, "VW Golf": 0.18,
    "Fiat Uno": 0.08, "Fiat Palio": 0.07, "Mercedes 190": 0.05,
}


@dataclass(frozen=True)
class SellingStyle:
    customers_per_day: tuple[float, float]  # range, for a Dacia Logan in the main branch, before seasons
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

# (part name, as a Moroccan counter writes it; category; real brands; selling style; price in MAD)
# Every (name, car) pair becomes one equivalent-parts group across its brands (same OEM number).
FAMILIES = [
    # Filters
    ("Filtre à huile", "Filters", ["Bosch", "Mann-Filter", "Purflux"], STEADY, 65),
    ("Filtre à air", "Filters", ["Mann-Filter", "Purflux", "Bosch"], STEADY, 95),
    ("Filtre habitacle", "Filters", ["Bosch", "Valeo", "Mann-Filter"], STEADY, 120),
    ("Filtre à gasoil", "Filters", ["Mann-Filter", "Purflux", "Bosch"], STEADY, 110),
    # Oils and fluids
    ("Huile moteur 5W30 5L", "Oils", ["Total", "Castrol", "Motul"], STEADY, 390),
    ("Huile moteur 10W40 5L", "Oils", ["Total", "Castrol", "Motul"], STEADY, 340),
    ("Liquide de frein", "Oils", ["Total", "Bosch", "Castrol"], SLOW, 70),
    ("Liquide de refroidissement 5L", "Oils", ["Total", "Motul", "Castrol"], SUMMER, 150),
    # Ignition
    ("Bougie d'allumage (jeu de 4)", "Ignition", ["NGK", "Bosch", "Febi Bilstein"], STEADY, 170),
    ("Bougie de préchauffage (jeu de 4)", "Ignition", ["Bosch", "NGK", "Febi Bilstein"], WINTER, 430),
    ("Bobine d'allumage", "Ignition", ["Valeo", "Bosch", "Febi Bilstein"], ERRATIC, 480),
    # Brakes
    ("Plaquettes de frein avant", "Brakes", ["TRW", "Bosch", "Ferodo"], ERRATIC, 330),
    ("Plaquettes de frein arrière", "Brakes", ["TRW", "Ferodo", "Febi Bilstein"], ERRATIC, 290),
    ("Disques de frein avant (paire)", "Brakes", ["TRW", "Brembo", "Febi Bilstein"], ERRATIC, 660),
    ("Disques de frein arrière (paire)", "Brakes", ["TRW", "Brembo", "Febi Bilstein"], SLOW, 600),
    ("Étrier de frein", "Brakes", ["TRW", "Bosch", "Febi Bilstein"], SLOW, 850),
    ("Flexible de frein", "Brakes", ["TRW", "Febi Bilstein"], SLOW, 85),
    # Lighting
    ("Ampoule de phare H7", "Lighting", ["Philips", "Osram", "Hella"], ERRATIC, 75),
    ("Ampoule de phare H4", "Lighting", ["Philips", "Osram", "Hella"], ERRATIC, 70),
    # Suspension and steering
    ("Amortisseur avant", "Suspension", ["Monroe", "Sachs"], LUMPY, 720),
    ("Amortisseur arrière", "Suspension", ["Monroe", "Sachs"], LUMPY, 680),
    ("Rotule de direction", "Suspension", ["TRW", "SKF"], SLOW, 180),
    ("Biellette de barre stabilisatrice", "Suspension", ["TRW", "SKF"], SLOW, 150),
    ("Roulement de roue", "Suspension", ["SKF", "TRW"], SLOW, 340),
    ("Silent bloc de suspension", "Suspension", ["Febi Bilstein", "SKF"], SLOW, 140),
    # Engine
    ("Kit de distribution", "Engine", ["Gates", "Dayco"], LUMPY, 950),
    ("Courroie d'accessoires", "Engine", ["Gates", "Dayco"], SLOW, 220),
    # Transmission
    ("Kit d'embrayage", "Transmission", ["Valeo", "Luk", "Sachs"], SLOW, 1850),
    # Electrical
    ("Alternateur", "Electrical", ["Valeo", "Bosch", "Denso"], SLOW, 2450),
    ("Démarreur", "Electrical", ["Valeo", "Bosch", "Denso"], SLOW, 1950),
    ("Batterie 70Ah", "Electrical", ["Varta", "Bosch"], BATTERY, 1150),
    ("Batterie 60Ah", "Electrical", ["Varta", "Bosch"], BATTERY, 980),
    ("Capteur ABS", "Electrical", ["Bosch", "Febi Bilstein"], SLOW, 280),
    # Cooling
    ("Pompe à eau", "Cooling", ["SKF", "Dayco", "Gates"], SLOW, 560),
    ("Radiateur", "Cooling", ["Valeo", "Nissens"], SUMMER, 1350),
    ("Ventilateur de refroidissement", "Cooling", ["Valeo", "Nissens"], SUMMER, 920),
    ("Thermostat", "Cooling", ["Wahler", "Valeo"], SLOW, 160),
    ("Durite de radiateur", "Cooling", ["Febi Bilstein", "Gates"], SLOW, 95),
    # Air conditioning
    ("Compresseur de climatisation", "Air conditioning", ["Valeo", "Denso"], SUMMER, 3600),
    ("Condenseur de climatisation", "Air conditioning", ["Valeo", "Nissens"], SUMMER, 1450),
    # Visibility
    ("Balai d'essuie-glace avant (paire)", "Visibility", ["Bosch", "Valeo"], WINTER, 155),
    ("Balai d'essuie-glace arrière", "Visibility", ["Bosch", "Valeo"], WINTER, 90),
]


@dataclass
class DemoPart:
    part: Part
    style: SellingStyle
    popularity: float  # 0 (never sells: dead stock) to 1 (a Dacia Logan at full demand)


def season_factor(days_of_year: np.ndarray, style: SellingStyle) -> np.ndarray:
    """Smooth bumps around 15 July (summer) and 15 January (winter)."""

    def bump(peak_day: int) -> np.ndarray:
        distance = np.abs(days_of_year - peak_day)
        distance = np.minimum(distance, 365 - distance)
        return np.exp(-((distance / 40.0) ** 2))

    return 1.0 + style.summer_boost * bump(196) + style.winter_boost * bump(15)


def eid_factor(ordinals: np.ndarray) -> np.ndarray:
    """A short rush in the days just before each Eid (cars made ready to travel for the family
    visit), then a quiet dip on the holiday itself (many shops close). Takes `date.toordinal()`
    values (a plain int per day), so it stays one vectorized numpy computation, not a Python loop
    over date objects — the only reason this runs fast enough for ~2,000 parts."""
    factor = np.ones(len(ordinals))
    for eid in [*EID_AL_FITR_DAYS, *EID_AL_ADHA_DAYS]:
        days_to_eid = eid.toordinal() - ordinals
        factor *= 1.0 + 0.4 * np.exp(-(((days_to_eid - 3) / 3.0) ** 2))
        factor *= 1.0 - 0.5 * np.exp(-((days_to_eid / 1.0) ** 2))
    return factor


def true_demand(
    rng: np.random.Generator, first_day: date, days: int, style: SellingStyle, branch_factor: float, popularity: float = 1.0
) -> np.ndarray:
    """Pieces customers wanted on each day: customers (Poisson) plus extra pieces they bought."""
    dates = [first_day + timedelta(days=i) for i in range(days)]
    weekdays = WEEKDAY_FACTORS[[d.weekday() for d in dates]]
    seasons = season_factor(np.array([d.timetuple().tm_yday for d in dates]), style)
    ramadan = np.where(ramadan_flags(first_day, days) > 0, RAMADAN_FACTOR, 1.0)
    eid = eid_factor(first_day.toordinal() + np.arange(days))
    trend = 1.0 + rng.uniform(-0.1, 0.2) * np.arange(days) / 365  # -10% to +20% a year
    base = rng.uniform(*style.customers_per_day) * branch_factor * popularity
    customers = rng.poisson(base * weekdays * seasons * ramadan * eid * trend)
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


def remove_demo_shop(db: Session, name: str) -> None:
    """Deletes the demo shop with this name and all its rows. Real shops (is_demo false) and the
    other demo shop (the big speed-test shop, app/demo/big_shop.py) are never touched."""
    demo_ids = db.scalars(select(Organization.id).where(Organization.is_demo, Organization.name == name)).all()
    if not demo_ids:
        return
    for table in reversed(Base.metadata.sorted_tables):
        if "organization_id" in table.c:
            db.execute(delete(table).where(table.c.organization_id.in_(demo_ids)))
    db.execute(delete(Organization).where(Organization.id.in_(demo_ids)))


def skip_reference_checks(db: Session) -> None:
    """For the rest of this transaction, PostgreSQL stops checking, row by row, that each new or
    deleted row's part, branch and shop exist (about 5 times faster for millions of demo rows; the
    demo makes every row itself, so none can point at a missing part). Needs the database's main
    user, which the app is in Docker. Demo shops only, never a real shop's data."""
    db.execute(text("SET LOCAL session_replication_role = replica"))


def create_demo_shop(
    db: Session, last_day: date, parts_count: int | None = None, history_days: int = HISTORY_DAYS, seed: int = 7
) -> tuple[Organization, Counter]:
    """Replaces any old demo shop with a new one whose sales history ends on `last_day`.
    Returns the shop and how many parts started out of stock, low, running out soon, or healthy."""
    rng = np.random.default_rng(seed)
    skip_reference_checks(db)
    remove_demo_shop(db, DEMO_SHOP_NAME)
    shop = Organization(name=DEMO_SHOP_NAME, currency="MAD", is_demo=True)
    db.add(shop)
    db.flush()
    # The same starting synonym list every real shop gets at setup (app/api/setup.py).
    db.add_all(SynonymGroup(organization_id=shop.id, words=words) for words in DEFAULT_SYNONYMS)
    branches = {Branch(organization_id=shop.id, name=name): factor for name, factor in BRANCHES.items()}
    db.add_all(branches)
    suppliers = make_suppliers(shop.id)
    db.add_all(suppliers)
    ids = random.Random(seed)  # apart from rng, so the made-up sales don't change
    give_seeded_ids([*branches, *suppliers], ids)
    db.flush()
    parts = _make_parts(shop.id, parts_count, rng, suppliers)
    give_seeded_ids([item.part for item in parts], ids)
    db.add_all(item.part for item in parts)
    db.flush()
    buckets = stock_buckets(rng, len(parts))

    first_day = last_day - timedelta(days=history_days - 1)
    series, outs = [], []
    counts = Counter()
    for item, bucket in zip(parts, buckets):
        group = []
        for branch, factor in branches.items():
            wanted = true_demand(rng, first_day, history_days + FUTURE_DAYS, item.style, factor, item.popularity)
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
        total = target_quantity(rng, bucket, item.part.min_stock, daily_rate, min_days)
        for s, quantity in zip(group, branch_quantities(rng, total, branch_rates)):
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


def target_quantity(rng: np.random.Generator, bucket: str, min_stock: int, daily_rate: float, min_days: float) -> int:
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


def make_suppliers(organization_id: uuid.UUID) -> list[Supplier]:
    return [
        Supplier(organization_id=organization_id, name=name, phone=phone, email=email, delivery_days=days,
                 delivery_source="file")  # as if from the shop's parts file, like the rest of the demo
        for name, phone, email, days in SUPPLIERS
    ]


def _make_parts(organization_id: uuid.UUID, parts_count: int | None, rng: np.random.Generator, suppliers: list[Supplier]) -> list[DemoPart]:
    """Every (family, car) pair gets one OEM number shared by all its brands — that's what makes
    them show up as equivalent parts. A car's popularity sets how much its parts sell; unpopular
    cars get a chance of a part that never sells at all (real dead stock, not just "slow")."""
    parts = []
    oem_numbers: dict[tuple[str, str], str] = {}
    for name, category, brands, style, price in FAMILIES:
        for car in CARS:
            oem = oem_numbers.setdefault((name, car), f"{rng.integers(1000, 9999)} {rng.integers(100, 999)} {rng.integers(100, 999)}")
            popularity = CAR_POPULARITY[car]
            for brand in brands:
                dead = rng.random() < max(0.0, 0.5 - popularity)
                supplier = suppliers[rng.integers(0, len(suppliers))]
                part = Part(
                    organization_id=organization_id,
                    sku=f"DEMO-{len(parts) + 1:04d}",
                    name=f"{name} - {car}",
                    brand=brand,
                    category=category,
                    oem_reference=oem,
                    unit_cost=price * 70,  # centimes: cost is 70% of the sale price
                    pack_size=PACK_SIZES.get(name, 1),
                    sale_price=price * 100,
                    supplier_id=supplier.id,
                )
                parts.append(DemoPart(part, style, 0.0 if dead else popularity))
    if parts_count is None or parts_count >= len(parts):
        return parts
    return [parts[i * len(parts) // parts_count] for i in range(parts_count)]  # spread over all families


def stock_buckets(rng: np.random.Generator, n: int) -> list[str]:
    """One bucket per part ("out", "low", "running_out" or "healthy"), shuffled, in the shares of
    STOCK_BUCKETS (rounding goes to "healthy", the largest and least sensitive share)."""
    counts = {name: round(n * share) for name, share in STOCK_BUCKETS}
    counts["healthy"] += n - sum(counts.values())
    buckets = [name for name, count in counts.items() for _ in range(count)]
    rng.shuffle(buckets)
    return buckets


def branch_quantities(rng: np.random.Generator, total: int, weights: np.ndarray) -> list[int]:
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
        for row_id, row in zip(increasing_ids(len(rows)), rows):
            copy.write_row((row_id, now, organization_id, *row))


def give_seeded_ids(rows: list, ids: random.Random) -> None:
    """Ids drawn from the seed instead of at random, so the same seed and last day rebuild the very
    same demo shop. The forecast lists parts in id order and the boosting model's sums depend a
    little on that order: with random ids, two rebuilds differed in the third decimal of
    check_forecasts, and check_orders and check_alerts sampled a different third of the parts."""
    for row in rows:
        row.id = uuid.UUID(int=ids.getrandbits(128), version=4)


def increasing_ids(count: int) -> list[uuid.UUID]:
    """New row ids in increasing order from a random start: PostgreSQL then adds them at the end
    of its id index instead of all over it (about 4 times faster for millions of demo rows)."""
    start = secrets.randbits(64) << 64
    return [uuid.UUID(int=start + n) for n in range(count)]


def main() -> None:
    refuse_demo_in_production()
    started = perf_counter()
    with SessionLocal() as db:
        shop, counts = create_demo_shop(db, last_day=date.today() - timedelta(days=1))
        password = add_demo_owner(db, shop)
        db.commit()
        lines = db.scalar(select(func.count()).select_from(SaleLine).where(SaleLine.organization_id == shop.id))
        print(f"Created '{DEMO_SHOP_NAME}' with {len(FAMILIES)} part families and {lines} sales lines in {perf_counter() - started:.0f} s.")
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
