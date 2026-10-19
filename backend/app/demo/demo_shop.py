"""A clearly labeled, made-up demo shop: about 200 parts, 3 branches, 18 months of daily sales.

It also saves the true demand it was made from (including stock-out days and 60 days after the
history ends), so forecasts can be checked against the truth. It always creates its own
organization marked is_demo and never touches a real shop.

Run inside Docker:  docker compose exec api python -m app.demo.demo_shop
"""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, utc_now
from app.forecast.calendar import ramadan_flags
from app.models import Branch, Organization, Part, SaleLine

DEMO_SHOP_NAME = "DEMO SHOP (made-up data)"
HISTORY_DAYS = 548  # 18 months
FUTURE_DAYS = 60  # true demand kept after the history ends, to check forecasts
BRANCHES = {"Casablanca - Maarif": 1.0, "Rabat - Agdal": 0.7, "Marrakech - Gueliz": 0.5}
# Monday..Sunday. Friday prayer shortens the day; most shops are closed on Sunday.
WEEKDAY_FACTORS = np.array([1.0, 1.0, 1.0, 1.0, 0.8, 1.05, 0.35])
RAMADAN_FACTOR = 0.7
STOCK_OUT_CHANCE = 0.35
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
) -> Organization:
    """Replaces any old demo shop with a new one whose sales history ends on `last_day`."""
    rng = np.random.default_rng(seed)
    remove_demo_shops(db)
    shop = Organization(name=DEMO_SHOP_NAME, currency="MAD", is_demo=True)
    db.add(shop)
    db.flush()
    branches = {Branch(organization_id=shop.id, name=name): factor for name, factor in BRANCHES.items()}
    db.add_all(branches)
    parts = _make_parts(shop.id, parts_count)
    db.add_all(item.part for item in parts)
    db.flush()

    first_day = last_day - timedelta(days=history_days - 1)
    sales, truth, outs, stock = [], [], [], []
    for item in parts:
        for branch, factor in branches.items():
            wanted = true_demand(rng, first_day, history_days + FUTURE_DAYS, item.style, factor)
            sold = wanted[:history_days].copy()
            periods = stock_out_periods(rng, history_days)
            for first, last in periods:
                sold[first : last + 1] = 0
                outs.append((item.part.id, branch.id, first_day + timedelta(days=first), first_day + timedelta(days=last)))
            key = (item.part.id, branch.id)
            sales += [(*key, first_day + timedelta(days=int(i)), int(sold[i]), item.part.sale_price) for i in np.flatnonzero(sold)]
            truth += [(*key, first_day + timedelta(days=int(i)), int(wanted[i])) for i in np.flatnonzero(wanted)]
            empty_now = any(last == history_days - 1 for _, last in periods)
            stock.append((*key, 0 if empty_now else int(rng.poisson(wanted[:history_days].mean() * 30 + 2))))

    _copy(db, "sale_lines", ["part_id", "branch_id", "sold_on", "quantity", "unit_price"], shop.id, sales)
    _copy(db, "demo_true_demand", ["part_id", "branch_id", "day", "quantity"], shop.id, truth)
    _copy(db, "stock_outs", ["part_id", "branch_id", "first_day", "last_day"], shop.id, outs)
    _copy(db, "stock_levels", ["part_id", "branch_id", "quantity"], shop.id, stock)
    return shop


def _make_parts(organization_id: uuid.UUID, parts_count: int | None) -> list[DemoPart]:
    parts = []
    for name, category, brands, style, count, price in FAMILIES:
        for i in range(count):
            part = Part(
                organization_id=organization_id,
                sku=f"DEMO-{len(parts) + 1:04d}",
                name=f"{name} - {CARS[i % len(CARS)]}",
                brand=brands[i % len(brands)],
                category=category,
                unit_cost=price * 70,  # centimes: cost is 70% of the sale price
                sale_price=price * 100,
                min_stock=2,
            )
            parts.append(DemoPart(part, style))
    if parts_count is None or parts_count >= len(parts):
        return parts
    return [parts[i * len(parts) // parts_count] for i in range(parts_count)]  # spread over all families


def _copy(db: Session, table: str, columns: list[str], organization_id: uuid.UUID, rows: list[tuple]) -> None:
    """Fast bulk insert with PostgreSQL COPY, inside the same transaction as the session."""
    now = utc_now()
    cursor = db.connection().connection.dbapi_connection.cursor()
    names = ", ".join(["id", "created_at", "organization_id", *columns])
    with cursor.copy(f"COPY {table} ({names}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row((uuid.uuid4(), now, organization_id, *row))


def main() -> None:
    with SessionLocal() as db:
        shop = create_demo_shop(db, last_day=date.today() - timedelta(days=1))
        db.commit()
        lines = db.scalar(select(func.count()).select_from(SaleLine).where(SaleLine.organization_id == shop.id))
        print(f"Created '{DEMO_SHOP_NAME}' with {len(FAMILIES)} part families and {lines} sales lines.")


if __name__ == "__main__":
    main()
