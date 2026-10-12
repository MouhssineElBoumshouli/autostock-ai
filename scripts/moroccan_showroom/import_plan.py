"""Read-only, idempotent import planning for the clean Moroccan target.

There is intentionally no record-writing adapter in this milestone. This module
turns the deterministic fixture into stable model/key/digest entries, compares
them with a read-only snapshot, and refuses conflicting prior fixture records.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib

from .generator import Dataset, canonical_json
from .safety import SafetyError


@dataclass(frozen=True)
class FixtureRecord:
    entity: str
    key: str
    payload_sha256: str


@dataclass(frozen=True)
class PlannedAction:
    entity: str
    key: str
    action: str
    payload_sha256: str


@dataclass(frozen=True)
class ImportPreview:
    dataset_version: str
    dataset_sha256: str
    actions: tuple[PlannedAction, ...]

    @property
    def counts(self) -> dict[str, int]:
        result = {"create": 0, "unchanged": 0}
        for item in self.actions:
            result[item.action] += 1
        return result


def fixture_records(dataset: Dataset) -> tuple[FixtureRecord, ...]:
    """Flatten planned Odoo records to stable natural keys without database IDs."""
    records: list[FixtureRecord] = []

    def add(entity: str, key: str, payload: dict) -> None:
        digest = hashlib.sha256(canonical_json(payload)).hexdigest()
        records.append(FixtureRecord(entity, key, digest))

    add(
        "company_configuration",
        "company_atlas_morocco",
        {
            "name": "Atlas Auto Distribution",
            "country": "MA",
            "city": "Marrakech",
            "timezone": "Africa/Casablanca",
            "currency": "MAD",
        },
    )
    for row in dataset.warehouses:
        add("warehouse", row["key"], row)
    for row in dataset.suppliers:
        add("supplier", row["key"], row)
    for row in dataset.customers:
        add("customer", row["key"], row)
    for product in dataset.products:
        add("product", product.key, asdict(product))
        for index, term in enumerate(product.supplier_terms, start=1):
            add(
                "supplier_term",
                f"{product.key}_supplier_term_{index:02d}",
                {"product_key": product.key, **asdict(term)},
            )
    for order in dataset.orders:
        add("completed_sale_order", order.key, asdict(order))
        for line in order.lines:
            add("completed_sale_line", line.key, asdict(line))
    for movement in dataset.movements:
        entity = {
            "opening_adjustment": "opening_adjustment",
            "vendor_receipt": "incoming_receipt",
            "customer_return": "linked_return",
            "internal_transfer": "internal_transfer",
            "sale_delivery": "sale_delivery_move_plan",
        }[movement.kind]
        add(entity, movement.key, asdict(movement))
    for order in dataset.open_orders:
        add("open_sale_order", order.key, asdict(order))
    for profile in dataset.history_profiles:
        add("history_profile_plan", profile["key"], profile)

    ordered = tuple(sorted(records, key=lambda item: (item.entity, item.key)))
    keys = [(item.entity, item.key) for item in ordered]
    if len(keys) != len(set(keys)):
        raise SafetyError("The generated fixture contains duplicate model/key identities.")
    return ordered


def preview_import(
    dataset: Dataset, existing: tuple[FixtureRecord, ...] = ()
) -> ImportPreview:
    """Plan creates/no-ops; reject duplicates or any content drift before writes."""
    planned = fixture_records(dataset)
    existing_keys = [(item.entity, item.key) for item in existing]
    if len(existing_keys) != len(set(existing_keys)):
        raise SafetyError("The read-only target snapshot contains duplicate fixture identities.")
    planned_keys = {(item.entity, item.key) for item in planned}
    existing_key_set = set(existing_keys)
    if existing_key_set and existing_key_set != planned_keys:
        raise SafetyError(
            "The target contains a partial or unexpected fixture set; restore a reviewed clean target."
        )
    current = {(item.entity, item.key): item.payload_sha256 for item in existing}
    actions = []
    for item in planned:
        previous = current.get((item.entity, item.key))
        if previous is None:
            action = "create"
        elif previous == item.payload_sha256:
            action = "unchanged"
        else:
            raise SafetyError(
                f"Existing fixture {item.entity}:{item.key} differs from this dataset version."
            )
        actions.append(PlannedAction(item.entity, item.key, action, item.payload_sha256))
    return ImportPreview(dataset.version, dataset.digest, tuple(actions))
