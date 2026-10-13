"""Build a deterministic, Odoo-neutral plan for the Moroccan demo dataset.

This module never imports Odoo and never connects to a database. Its output is
fixture input for a separately reviewed importer, not business validation.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
import hashlib
from importlib.resources import files
import json
import random
from zoneinfo import ZoneInfo

from .catalog import CATEGORIES, CUSTOMERS, DEMAND_CLASSES, SUPPLIERS, WAREHOUSES

DATASET_VERSION = "atlas-ma-2026.4"
DEFAULT_SEED = 36036
MISSING_SUPPLIER_SKU = "AT-MA-FLT-132"
FOCUS_START = date(2026, 7, 1)
HISTORY_START = date(2026, 4, 13)
END_DATE = date(2026, 10, 10)
HISTORY_PROFILE_SKUS = frozenset(
    f"AT-MA-{category_code}-{number:03d}"
    for category_code in ("FLT", "BRK", "SUS", "ELC", "CLD", "IGN")
    for number in range(101, 105)
)
FORECAST_PROFILE_COUNT = len(HISTORY_PROFILE_SKUS)
WAREHOUSE_HISTORY_PROFILE_SKUS = {
    "warehouse_atlas_central": (
        "AT-MA-FLT-101",
        "AT-MA-BRK-102",
        "AT-MA-SUS-103",
    ),
    "warehouse_south_depot": (
        "AT-MA-FLT-101",
        "AT-MA-BRK-102",
        "AT-MA-SUS-103",
    ),
}
WAREHOUSE_FORECAST_PROFILE_COUNT = sum(
    len(skus) for skus in WAREHOUSE_HISTORY_PROFILE_SKUS.values()
)
with files("tzdata.zoneinfo").joinpath("Africa", "Casablanca").open("rb") as _zonefile:
    # Read the pinned IANA rules from the dependency instead of the host OS.
    # This keeps Windows and container builds byte-identical after Morocco's
    # announced September 2026 transition is reflected in tzdata.
    LOCAL_ZONE = ZoneInfo.from_file(_zonefile, key="Africa/Casablanca")


@dataclass(frozen=True)
class SupplierTerm:
    supplier_key: str
    vendor_code: str
    lead_days: int
    currency: str
    ordering_uom: str
    moq: int
    price_tiers: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class Product:
    key: str
    sku: str
    category: str
    name: str
    inventory_uom: str
    sale_price_mad: int
    supplier_terms: tuple[SupplierTerm, ...]
    reorder_minimum: int | None
    reorder_maximum: int | None
    demand_class: str
    history_profile_key: str | None


@dataclass(frozen=True)
class SaleLine:
    key: str
    sku: str
    quantity: int
    movement_key: str


@dataclass(frozen=True)
class Order:
    key: str
    day: date
    customer_key: str
    state: str
    lines: tuple[SaleLine, ...]
    warehouse_key: str


@dataclass(frozen=True)
class Movement:
    key: str
    day: date
    kind: str
    sku: str
    quantity: int
    source: str
    destination: str
    order_key: str | None = None
    partner_key: str | None = None
    original_movement_key: str | None = None
    journey_key: str | None = None
    effective_at_utc: str | None = None


@dataclass(frozen=True)
class OpenOrder:
    key: str
    day: date
    customer_key: str
    sku: str
    quantity: int
    warehouse_key: str
    reservation_policy: str


@dataclass(frozen=True)
class Dataset:
    version: str
    seed: int
    products: tuple[Product, ...]
    suppliers: tuple[dict, ...]
    customers: tuple[dict, ...]
    warehouses: tuple[dict, ...]
    orders: tuple[Order, ...]
    open_orders: tuple[OpenOrder, ...]
    movements: tuple[Movement, ...]
    daily_observations: tuple[dict, ...]
    history_profiles: tuple[dict, ...]
    ending_on_hand: tuple[dict, ...]
    counts: dict
    digest: str

    def as_dict(self) -> dict:
        """Return a stable JSON-ready representation with ISO date values."""
        return _jsonable(asdict(self))


def _jsonable(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def _event_time_utc(day: date) -> str:
    local_time = datetime.combine(day, time(12, 0), tzinfo=LOCAL_ZONE)
    return local_time.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def _profiled_products(products: tuple[Product, ...]) -> tuple[Product, ...]:
    """Return the 24 explicitly selected history examples in catalog order."""
    selected = tuple(product for product in products if product.sku in HISTORY_PROFILE_SKUS)
    if len(selected) != FORECAST_PROFILE_COUNT:
        raise AssertionError("The selected historical product keys do not match the catalog.")
    return selected


def _product_catalog(seed: int) -> tuple[Product, ...]:
    rng = random.Random(seed)
    products = []
    global_index = 0
    for category in CATEGORIES:
        for category_index in range(category["count"]):
            family = category["families"][category_index % len(category["families"])]
            series = category_index // len(category["families"]) + 1
            name = family if series == 1 else f"{family} (Series {series})"
            sku = f"AT-MA-{category['code']}-{category_index + 101:03d}"
            supplier_key = category["suppliers"][category_index % len(category["suppliers"])]
            supplier = next(item for item in SUPPLIERS if item[0] == supplier_key)
            sale_price = rng.randrange(category["price"][0], category["price"][1] + 1, 5)
            base_cost = max(15, sale_price * rng.randrange(48, 72) // 100)
            moq = (1, 2, 4, 6, 12)[category_index % 5]
            tier_threshold = max(moq * 4, 8)
            terms = [
                SupplierTerm(
                    supplier_key=supplier_key,
                    vendor_code=f"{supplier[0].upper()}-{category['code']}-{category_index + 1:03d}",
                    lead_days=(4, 6, 8, 9, 12)[category_index % 5],
                    currency="MAD",
                    ordering_uom="unit",
                    moq=moq,
                    price_tiers=((moq, base_cost), (tier_threshold, max(1, base_cost - max(1, base_cost // 12)))),
                )
            ]
            if category_index % 7 == 0:
                second_key = category["suppliers"][(category_index + 1) % len(category["suppliers"])]
                second_supplier = next(item for item in SUPPLIERS if item[0] == second_key)
                terms.append(
                    SupplierTerm(
                        supplier_key=second_key,
                        vendor_code=f"{second_supplier[0].upper()}-{category['code']}-{category_index + 1:03d}",
                        lead_days=(5, 7, 10)[category_index % 3],
                        currency="MAD",
                        ordering_uom="unit",
                        moq=1,
                        price_tiers=((1, base_cost + max(1, base_cost // 20)),),
                    )
                )
            demand_class = DEMAND_CLASSES[category_index % len(DEMAND_CLASSES)]
            key = f"product_{sku.lower().replace('-', '_')}"
            products.append(
                Product(
                    key=key,
                    sku=sku,
                    category=category["key"],
                    name=name,
                    inventory_uom="unit",
                    sale_price_mad=sale_price,
                    supplier_terms=() if sku == MISSING_SUPPLIER_SKU else tuple(terms),
                    reorder_minimum=(
                        None if sku == MISSING_SUPPLIER_SKU
                        else (3, 5, 8, 10, 12, 18)[global_index % 6]
                    ),
                    reorder_maximum=(
                        None if sku == MISSING_SUPPLIER_SKU
                        else (14, 24, 30, 36, 48, 72)[global_index % 6]
                    ),
                    demand_class=demand_class,
                    history_profile_key=(
                        f"history_{sku.lower().replace('-', '_')}"
                        if sku in HISTORY_PROFILE_SKUS
                        else None
                    ),
                )
            )
            global_index += 1
    return tuple(products)


def _history_sales(products: tuple[Product, ...], rng: random.Random) -> list[tuple[date, str, int, str, str]]:
    """Create pre-focus deliveries for 24 explicitly covered series."""
    probabilities = {"fast": 0.62, "steady": 0.38, "intermittent": 0.18, "slow": 0.09}
    quantities = {"fast": (2, 3, 4, 6), "steady": (1, 2, 3), "intermittent": (1, 2), "slow": (1,)}
    results = []
    customer_keys = [item[0] for item in CUSTOMERS]
    history_products = _profiled_products(products)
    day = HISTORY_START
    while day < FOCUS_START:
        for product_index, product in enumerate(history_products):
            product_rng = random.Random(rng.randrange(1, 2**31) + product_index)
            if product_rng.random() < probabilities[product.demand_class]:
                customer = customer_keys[(product_index + day.toordinal()) % len(customer_keys)]
                quantity = product_rng.choice(quantities[product.demand_class])
                key = f"SO-MA-H-{day:%Y%m%d}-{product_index + 1:02d}"
                results.append((day, product.sku, quantity, customer, key))
        day += timedelta(days=1)
    return results


def _warehouse_history_sales(
    products: tuple[Product, ...], seed: int
) -> list[tuple[date, str, int, str, str, str]]:
    """Create independent ASD sales for the small, explicitly scoped sample.

    Per-day seeds keep this series independent from the ATC history and from
    the focus-window generator. These are separate fictional orders, not a
    second label for company-wide or ATC demand.
    """
    probabilities = {"fast": 0.62, "steady": 0.38, "intermittent": 0.18, "slow": 0.09}
    quantities = {"fast": (2, 3, 4, 6), "steady": (1, 2, 3), "intermittent": (1, 2), "slow": (1,)}
    product_by_sku = {product.sku: product for product in products}
    customer_keys = [item[0] for item in CUSTOMERS]
    selected = WAREHOUSE_HISTORY_PROFILE_SKUS["warehouse_south_depot"]
    results = []
    day = HISTORY_START
    while day < FOCUS_START:
        for product_index, sku in enumerate(selected):
            product = product_by_sku[sku]
            seed_material = f"{seed}:ASD:{sku}:{day.isoformat()}".encode("ascii")
            day_seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big")
            product_rng = random.Random(day_seed)
            if product_rng.random() < probabilities[product.demand_class]:
                customer = customer_keys[(product_index + day.toordinal()) % len(customer_keys)]
                quantity = product_rng.choice(quantities[product.demand_class])
                key = f"SO-MA-H-ASD-{day:%Y%m%d}-{product_index + 1:02d}"
                results.append(
                    (day, sku, quantity, customer, key, "warehouse_south_depot")
                )
        day += timedelta(days=1)
    return results


def _warehouse_profile_key(sku: str, warehouse_key: str) -> str:
    return f"warehouse_history_{warehouse_key.removeprefix('warehouse_')}_{sku.lower().replace('-', '_')}"


def _movement_warehouse(movement: Movement) -> str | None:
    """Attribute demand and returns to the warehouse of the original delivery."""
    if movement.kind == "sale_delivery":
        return movement.source
    if movement.kind == "customer_return":
        return movement.destination
    return None


def _movement_priority(movement: Movement) -> tuple[date, int, str]:
    priority = {
        "opening_adjustment": 0,
        "vendor_receipt": 1,
        "customer_return": 2,
        "internal_transfer": 3,
        "sale_delivery": 4,
    }.get(movement.kind, 5)
    return movement.day, priority, movement.key


def _location_deltas(movement: Movement) -> tuple[tuple[str, int], ...]:
    if movement.kind == "opening_adjustment":
        return ((movement.destination, movement.quantity),)
    if movement.kind in {"vendor_receipt", "customer_return"}:
        return ((movement.destination, movement.quantity),)
    if movement.kind == "sale_delivery":
        return ((movement.source, -movement.quantity),)
    if movement.kind == "internal_transfer":
        return ((movement.source, -movement.quantity), (movement.destination, movement.quantity))
    raise ValueError(f"Unsupported stock movement kind: {movement.kind}")


def _add_opening_adjustments(
    products: tuple[Product, ...], movements: list[Movement], orders: list[Order]
) -> tuple[list[Movement], tuple[dict, ...]]:
    """Add native adjustment plans that keep each location ledger nonnegative."""
    by_sku = {product.sku: product for product in products}
    locations = [item[0] for item in WAREHOUSES]
    opening_events = []
    all_pairs = {(product.sku, location) for product in products for location in locations}

    for sku, location in sorted(all_pairs):
        relevant = [item for item in movements if item.sku == sku and location in {item.source, item.destination}]
        running = 0
        lowest = 0
        for item in sorted(relevant, key=_movement_priority):
            for changed_location, delta in _location_deltas(item):
                if changed_location == location:
                    running += delta
                    lowest = min(lowest, running)

        product_index = next(i for i, product in enumerate(products) if product.sku == sku)
        product = by_sku[sku]
        is_central = location == WAREHOUSES[0][0]
        desired_buffer = 0
        if sku == MISSING_SUPPLIER_SKU:
            # A visible supplier-gap example with modest, stable opening stock.
            # It has no configured reorder policy, so the risk service cannot
            # invent a suggested quantity for a part with no vendor terms.
            desired_buffer = 8 if is_central else 5
        elif is_central:
            if product_index % 10 == 0:
                desired_buffer = 0
            elif product_index % 10 == 1:
                desired_buffer = 1
            elif product_index % 10 == 2:
                desired_buffer = product.reorder_maximum + 12
            else:
                desired_buffer = product.reorder_minimum + 6
            if 30 <= product_index < 50:
                desired_buffer = max(desired_buffer, 5)
        elif product_index % 3 == 0:
            desired_buffer = max(1, product.reorder_minimum // 2)

        initial = max(0, -lowest, desired_buffer - running)
        if initial:
            effective_day = HISTORY_START if product.history_profile_key else FOCUS_START
            opening_events.append(
                Movement(
                    key=f"OPEN-{sku}-{location}",
                    day=effective_day,
                    kind="opening_adjustment",
                    sku=sku,
                    quantity=initial,
                    source="inventory_adjustment",
                    destination=location,
                    effective_at_utc=_event_time_utc(effective_day),
                )
            )
            if initial + running < 0:
                raise AssertionError(f"Opening stock planning left {sku} negative in {location}.")
        elif running < 0:
            raise AssertionError(f"Opening stock planning left {sku} negative in {location}.")

    all_movements = sorted(opening_events + movements, key=_movement_priority)
    live = defaultdict(int)
    ending = []
    for movement in all_movements:
        for location, delta in _location_deltas(movement):
            live[(movement.sku, location)] += delta
            if live[(movement.sku, location)] < 0:
                raise AssertionError(
                    f"Negative intermediate stock for {movement.sku} at {location} on {movement.day}."
                )
    for sku, location in sorted(all_pairs):
        ending.append(
            {
                "sku": sku,
                "warehouse_key": location,
                "on_hand": live[(sku, location)],
                "uom": "unit",
            }
        )
    return all_movements, tuple(ending)


def generate_dataset(seed: int = DEFAULT_SEED) -> Dataset:
    """Build the same typed fixture plan for a given seed and version."""
    if not isinstance(seed, int) or seed < 0:
        raise ValueError("The generator seed must be a nonnegative integer.")

    rng = random.Random(seed)
    products = _product_catalog(seed)
    history_products = _profiled_products(products)
    product_by_index = list(products)
    customer_keys = [item[0] for item in CUSTOMERS]
    warehouse_keys = [item[0] for item in WAREHOUSES]
    orders: list[Order] = []
    movement_events: list[Movement] = []

    # The original April-June series is scoped to ATC. A separate, seeded
    # stream adds real ASD sales only for the small, explicitly scoped sample.
    for day, sku, quantity, customer_key, order_key in _history_sales(products, rng):
        warehouse_key = warehouse_keys[0]
        movement_key = f"DEL-{order_key}-01"
        line = SaleLine(f"LINE-{order_key}-01", sku, quantity, movement_key)
        orders.append(Order(order_key, day, customer_key, "delivered", (line,), warehouse_key))
        movement_events.append(
            Movement(
                movement_key,
                day,
                "sale_delivery",
                sku,
                quantity,
                warehouse_key,
                "customer_location",
                order_key=order_key,
                partner_key=customer_key,
                effective_at_utc=_event_time_utc(day),
            )
        )
    for day, sku, quantity, customer_key, order_key, warehouse_key in _warehouse_history_sales(products, seed):
        movement_key = f"DEL-{order_key}-01"
        line = SaleLine(f"LINE-{order_key}-01", sku, quantity, movement_key)
        orders.append(Order(order_key, day, customer_key, "delivered", (line,), warehouse_key))
        movement_events.append(
            Movement(
                movement_key,
                day,
                "sale_delivery",
                sku,
                quantity,
                warehouse_key,
                "customer_location",
                order_key=order_key,
                partner_key=customer_key,
                effective_at_utc=_event_time_utc(day),
            )
        )

    focus_orders = []
    sales_candidates = [product for product in product_by_index if product.sku != MISSING_SUPPLIER_SKU]
    for order_index in range(350):
        order_key = f"SO-MA-{FOCUS_START.year}-{order_index + 1:04d}"
        day = (
            END_DATE
            if order_index == 349
            else FOCUS_START + timedelta(days=rng.randrange((END_DATE - FOCUS_START).days + 1))
        )
        warehouse_key = warehouse_keys[order_index % len(warehouse_keys)]
        customer_key = customer_keys[(order_index * 7 + rng.randrange(len(customer_keys))) % len(customer_keys)]
        line_count = 1 + order_index % 5
        lines = []
        for line_index in range(line_count):
            if order_index == 349 and line_index in {0, 1}:
                product = product_by_index[line_index]
            elif order_index == 349:
                candidates = [product for product in sales_candidates if product not in product_by_index[:2]]
                product = rng.choice(candidates)
            elif order_index < FORECAST_PROFILE_COUNT and line_index == 0:
                product = history_products[order_index]
            else:
                product = rng.choice(sales_candidates)
            if order_index == 349 and line_index == 0:
                quantity = 3
            elif order_index == 349 and line_index == 1:
                quantity = 2
            else:
                quantity = rng.choice((1, 1, 2, 2, 3, 4, 6))
            movement_key = f"DEL-{order_key}-{line_index + 1:02d}"
            lines.append(SaleLine(f"LINE-{order_key}-{line_index + 1:02d}", product.sku, quantity, movement_key))
            movement_events.append(
                Movement(
                    movement_key,
                    day,
                    "sale_delivery",
                    product.sku,
                    quantity,
                    warehouse_key,
                    "customer_location",
                    order_key=order_key,
                    partner_key=customer_key,
                    effective_at_utc=_event_time_utc(day),
                )
            )
        order = Order(order_key, day, customer_key, "delivered", tuple(lines), warehouse_key)
        orders.append(order)
        focus_orders.append(order)

    receipts = []
    receiptable_products = [product for product in product_by_index if product.supplier_terms]
    for index in range(30):
        product = receiptable_products[(index * 11 + 8) % len(receiptable_products)]
        day = FOCUS_START + timedelta(days=rng.randrange((END_DATE - FOCUS_START).days + 1))
        warehouse = warehouse_keys[index % len(warehouse_keys)]
        supplier_key = product.supplier_terms[index % len(product.supplier_terms)].supplier_key
        movement = Movement(
            f"IN-MA-{index + 1:03d}",
            day,
            "vendor_receipt",
            product.sku,
            rng.randrange(6, 31),
            "supplier_location",
            warehouse,
            partner_key=supplier_key,
            effective_at_utc=_event_time_utc(day),
        )
        receipts.append(movement)
    movement_events.extend(receipts)

    completed_lines = [
        (order, line)
        for order in orders
        if order.state == "delivered"
        for line in order.lines
        if line.quantity >= 1 and order.day < END_DATE
    ]
    # Retain at least one genuinely linked return in each warehouse-specific
    # sample. The remaining returns are selected from the same deterministic
    # completed-order pool and keep the dataset's existing total of twelve.
    return_targets = []
    target_sku = WAREHOUSE_HISTORY_PROFILE_SKUS["warehouse_atlas_central"][0]
    for warehouse_key in warehouse_keys:
        target = next(
            (
                (order, line)
                for order, line in completed_lines
                if order.day < FOCUS_START
                and order.warehouse_key == warehouse_key
                and line.sku == target_sku
            ),
            None,
        )
        if not target:
            raise AssertionError(f"The deterministic history has no return candidate for {warehouse_key}.")
        return_targets.append(target)
    target_line_keys = {line.key for _order, line in return_targets}
    return_pool = [pair for pair in completed_lines if pair[1].key not in target_line_keys]
    rng.shuffle(return_pool)
    returns = []
    for index, (original_order, original_line) in enumerate(return_targets + return_pool[:10]):
        return_day = min(END_DATE, original_order.day + timedelta(days=2 + index % 19))
        if return_day <= original_order.day:
            return_day = END_DATE
        return_move = Movement(
            f"RET-MA-{index + 1:03d}",
            return_day,
            "customer_return",
            original_line.sku,
            1,
            "customer_location",
            original_order.warehouse_key,
            order_key=original_order.key,
            partner_key=original_order.customer_key,
            original_movement_key=original_line.movement_key,
            effective_at_utc=_event_time_utc(return_day),
        )
        returns.append(return_move)
    movement_events.extend(returns)

    transfers = []
    transferable_products = [product for product in product_by_index if product.supplier_terms]
    for index in range(18):
        product = transferable_products[(index * 13 + 4) % len(transferable_products)]
        day = FOCUS_START + timedelta(days=rng.randrange((END_DATE - FOCUS_START).days + 1))
        from_central = index % 2 == 0
        source, destination = (
            (warehouse_keys[0], warehouse_keys[1])
            if from_central
            else (warehouse_keys[1], warehouse_keys[0])
        )
        transfer = Movement(
            f"MOVE-MA-{index + 1:03d}",
            day,
            "internal_transfer",
            product.sku,
            rng.randrange(1, 7),
            source,
            destination,
            journey_key=f"TRANSFER-MA-{index + 1:03d}",
            effective_at_utc=_event_time_utc(day),
        )
        transfers.append(transfer)
    movement_events.extend(transfers)

    open_orders = []
    open_order_products = [
        product for product in product_by_index[30:]
        if product.sku != MISSING_SUPPLIER_SKU
    ][:20]
    if len(open_order_products) != 20:
        raise AssertionError("The generated open-order pool must contain twenty supplier-covered products.")
    for index in range(20):
        product = open_order_products[index]
        day = END_DATE - timedelta(days=index % 10)
        open_orders.append(
            OpenOrder(
                f"SO-MA-OPEN-{index + 1:03d}",
                day,
                customer_keys[(index * 5) % len(customer_keys)],
                product.sku,
                2 if index % 2 == 0 else 1,
                warehouse_keys[0],
                "reserve_with_native_odoo_rules_when_available_otherwise_wait",
            )
        )

    movements, ending_on_hand = _add_opening_adjustments(products, movement_events, orders)

    delivered_by_day_sku = Counter()
    returned_by_day_sku = Counter()
    event_count_by_day_sku = Counter()
    warehouse_delivered = Counter()
    warehouse_returned = Counter()
    warehouse_event_count = Counter()
    for movement in movements:
        if movement.kind not in {"sale_delivery", "customer_return"}:
            continue
        key = (movement.sku, movement.day)
        warehouse_key = _movement_warehouse(movement)
        if movement.kind == "sale_delivery":
            delivered_by_day_sku[key] += movement.quantity
            event_count_by_day_sku[key] += 1
            warehouse_delivered[(movement.sku, warehouse_key, movement.day)] += movement.quantity
            warehouse_event_count[(movement.sku, warehouse_key, movement.day)] += 1
        else:
            returned_by_day_sku[key] += movement.quantity
            event_count_by_day_sku[key] += 1
            warehouse_returned[(movement.sku, warehouse_key, movement.day)] += movement.quantity
            warehouse_event_count[(movement.sku, warehouse_key, movement.day)] += 1

    daily_observations = []
    history_days = (END_DATE - HISTORY_START).days + 1
    product_by_sku = {product.sku: product for product in history_products}
    profile_specs = [
        (product, None, product.history_profile_key)
        for product in history_products
    ]
    profile_specs.extend(
        (
            product_by_sku[sku],
            warehouse_key,
            _warehouse_profile_key(sku, warehouse_key),
        )
        for warehouse_key, skus in WAREHOUSE_HISTORY_PROFILE_SKUS.items()
        for sku in skus
    )
    for product, warehouse_key, profile_key in profile_specs:
        day = HISTORY_START
        while day <= END_DATE:
            if warehouse_key:
                day_key = (product.sku, warehouse_key, day)
                delivered_units = warehouse_delivered[day_key]
                returned_units = warehouse_returned[day_key]
                source_event_count = warehouse_event_count[day_key]
            else:
                day_key = (product.sku, day)
                delivered_units = delivered_by_day_sku[day_key]
                returned_units = returned_by_day_sku[day_key]
                source_event_count = event_count_by_day_sku[day_key]
            daily_observations.append(
                {
                    "profile_key": profile_key,
                    "sku": product.sku,
                    "warehouse_key": warehouse_key,
                    "day": day,
                    "delivered_units": delivered_units,
                    "returned_units": returned_units,
                    "source_event_count": source_event_count,
                    "coverage_complete": True,
                }
            )
            day += timedelta(days=1)
    expected_observation_rows = (
        FORECAST_PROFILE_COUNT + WAREHOUSE_FORECAST_PROFILE_COUNT
    ) * history_days
    if len(daily_observations) != expected_observation_rows:
        raise AssertionError("The generated forecast coverage has a missing calendar day.")
    history_profiles = []
    for product, warehouse_key, profile_key in profile_specs:
        source_events = [
            item
            for item in movements
            if item.sku == product.sku and item.kind in {"sale_delivery", "customer_return"}
            and (warehouse_key is None or _movement_warehouse(item) == warehouse_key)
        ]
        profile_rows = [item for item in daily_observations if item["profile_key"] == profile_key]
        nonzero_delivery_days = sum(row["delivered_units"] > 0 for row in profile_rows)
        if nonzero_delivery_days < 7:
            raise AssertionError(
                f"The planned {warehouse_key or 'company-wide'} history for {product.sku} "
                "has fewer than seven nonzero delivery days."
            )
        profile_digest = hashlib.sha256(canonical_json(_jsonable(profile_rows))).hexdigest()
        history_profiles.append(
            {
                "key": profile_key,
                "sku": product.sku,
                "category": product.category,
                "demand_class": product.demand_class,
                "warehouse_key": warehouse_key,
                "dataset_version": DATASET_VERSION,
                "business_effective_start": HISTORY_START,
                "business_effective_end": END_DATE,
                "calendar_days": history_days,
                "planned_qualifying_move_count": len(source_events),
                "planned_delivery_move_count": sum(item.kind == "sale_delivery" for item in source_events),
                "planned_return_move_count": sum(item.kind == "customer_return" for item in source_events),
                "planned_delivery_units": sum(item.quantity for item in source_events if item.kind == "sale_delivery"),
                "planned_returned_units": sum(item.quantity for item in source_events if item.kind == "customer_return"),
                "planned_nonzero_delivery_days": nonzero_delivery_days,
                "planned_daily_rows_sha256": profile_digest,
                "status": "fixture_plan_only_not_verified_in_odoo",
            }
        )

    supplied = tuple(
        {"key": key, "name": name, "city": city, "country": "MA", "fictional": True}
        for key, name, city in SUPPLIERS
    )
    customers = tuple(
        {"key": key, "name": name, "city": city, "country": "MA", "fictional": True}
        for key, name, city in CUSTOMERS
    )
    warehouses = tuple(
        {"key": key, "name": name, "code": code, "city": city}
        for key, name, code, city in WAREHOUSES
    )
    orders.sort(key=lambda order: (order.day, order.key))
    movements.sort(key=_movement_priority)
    focus_completed = len(focus_orders)
    counts = {
        "companies": 1,
        "warehouses": len(warehouses),
        "products": len(products),
        "products_without_supplier_terms": sum(not product.supplier_terms for product in products),
        "reordering_rules": sum(
            2 for product in products if product.reorder_minimum is not None and product.reorder_maximum is not None
        ),
        "suppliers": len(supplied),
        "customers": len(customers),
        "focus_completed_orders": focus_completed,
        "focus_completed_delivery_lines": sum(
            len(order.lines)
            for order in orders
            if order.state == "delivered"
            and FOCUS_START <= order.day <= END_DATE
        ),
        "history_orders_before_focus": sum(1 for order in orders if order.day < FOCUS_START),
        "receipt_pickings": sum(item.kind == "vendor_receipt" for item in movements),
        "linked_customer_returns": sum(item.kind == "customer_return" for item in movements),
        "internal_transfer_journeys": sum(item.kind == "internal_transfer" for item in movements),
        "open_customer_orders": len(open_orders),
        "history_profiles": len(history_profiles),
        "companywide_history_profiles": FORECAST_PROFILE_COUNT,
        "warehouse_history_profiles": WAREHOUSE_FORECAST_PROFILE_COUNT,
        "history_daily_observation_rows": len(daily_observations),
        "history_profile_category_mix": dict(
            sorted(Counter(product.category for product in history_products).items())
        ),
        "history_profile_demand_class_mix": dict(
            sorted(Counter(product.demand_class for product in history_products).items())
        ),
        "warehouse_history_profile_category_mix": dict(
            sorted(
                Counter(
                    item[0].category
                    for item in profile_specs
                    if item[1] is not None
                ).items()
            )
        ),
        "warehouse_history_profile_scope_mix": dict(
            sorted(Counter(item[1] for item in profile_specs if item[1] is not None).items())
        ),
        "warehouse_history_orders_before_focus": sum(
            order.day < FOCUS_START and order.warehouse_key == "warehouse_south_depot"
            for order in orders
        ),
        "history_calendar_days_per_profile": history_days,
        "history_profile_move_count": sum(item["planned_qualifying_move_count"] for item in history_profiles),
        "opening_adjustments": sum(item.kind == "opening_adjustment" for item in movements),
    }
    if counts["focus_completed_orders"] != 350:
        raise AssertionError("The focus dataset must contain exactly 350 completed orders.")
    if counts["receipt_pickings"] != 30 or counts["linked_customer_returns"] != 12:
        raise AssertionError("Receipt and return target counts drifted.")
    if counts["internal_transfer_journeys"] != 18 or counts["open_customer_orders"] != 20:
        raise AssertionError("Transfer or open-order target counts drifted.")

    payload = {
        "version": DATASET_VERSION,
        "seed": seed,
        "products": _jsonable([asdict(item) for item in products]),
        "suppliers": supplied,
        "customers": customers,
        "warehouses": warehouses,
        "orders": _jsonable([asdict(item) for item in orders]),
        "open_orders": _jsonable([asdict(item) for item in open_orders]),
        "movements": _jsonable([asdict(item) for item in movements]),
        "daily_observations": _jsonable(daily_observations),
        "history_profiles": _jsonable(history_profiles),
        "ending_on_hand": _jsonable(ending_on_hand),
        "counts": counts,
    }
    digest = hashlib.sha256(canonical_json(payload)).hexdigest()
    return Dataset(
        version=DATASET_VERSION,
        seed=seed,
        products=products,
        suppliers=supplied,
        customers=customers,
        warehouses=warehouses,
        orders=tuple(orders),
        open_orders=tuple(open_orders),
        movements=tuple(movements),
        daily_observations=tuple(daily_observations),
        history_profiles=tuple(history_profiles),
        ending_on_hand=ending_on_hand,
        counts=counts,
        digest=digest,
    )


def canonical_json(value: dict | list) -> bytes:
    """Serialize fixture plans identically across platforms."""
    return (
        json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
