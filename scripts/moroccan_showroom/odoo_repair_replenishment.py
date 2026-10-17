"""One-time guarded repair for auto-generated Moroccan replenishment moves.

This script is intentionally narrow. It only repairs the already-imported
atlas-ma-2026.4 showroom after proving the live target still matches the exact
scheduler-drift signature diagnosed on 2026-10-17. The transaction is committed
only after the normal importer dry-run audit passes again.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys


EXPECTED_DATASET_VERSION = "atlas-ma-2026.4"
EXPECTED_UNEXPECTED_MOVE_COUNT = 165
EXPECTED_ORDERPOINT_COUNT = 298


def _load_fixture_package():
    try:
        return importlib.import_module("scripts.moroccan_showroom")
    except ImportError:
        package_path = Path(__file__).resolve().parent
        spec = importlib.util.spec_from_file_location(
            "autostock_moroccan_showroom",
            package_path / "__init__.py",
            submodule_search_locations=[str(package_path)],
        )
        if not spec or not spec.loader:
            raise RuntimeError("The Moroccan fixture package could not be loaded.")
        package = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = package
        spec.loader.exec_module(package)
        return package


package = _load_fixture_package()
generator = importlib.import_module(f"{package.__name__}.generator")
import_plan = importlib.import_module(f"{package.__name__}.import_plan")
importer = importlib.import_module(f"{package.__name__}.odoo_importer")

typed_uuid = os.environ.get("AUTOSTOCK_MOROCCO_TYPED_TARGET_UUID", "")
prepared_uuid = os.environ.get("AUTOSTOCK_DEMO_TARGET_UUID", "")
if not typed_uuid or typed_uuid != prepared_uuid:
    raise RuntimeError("Repair requires the exact prepared Moroccan target UUID.")

dataset = generator.generate_dataset()
if dataset.version != EXPECTED_DATASET_VERSION:
    raise RuntimeError("Repair script dataset version does not match the approved showroom version.")

company = env.ref("base.main_company")
params = env["ir.config_parameter"]
if (
    not company.autostock_demo_environment
    or company.autostock_demo_target_uuid != prepared_uuid
    or params.get_param("autostock.morocco.target_uuid") != prepared_uuid
):
    raise RuntimeError("Repair target markers do not match the prepared Moroccan target.")
if company.autostock_demo_dataset_version != dataset.version:
    raise RuntimeError("Repair target does not contain the expected imported dataset.")

registry = env["autostock.morocco.fixture"].search([], order="fixture_key, id")
expected_registry_count = len(import_plan.fixture_records(dataset))
expected_forecasts = 3 * len(dataset.history_profiles)
if len(registry) != expected_registry_count:
    raise RuntimeError(
        f"Repair requires the complete fixture registry ({expected_registry_count}); found {len(registry)}."
    )
if registry.search_count([("entity", "=", "forecast_request")]) != expected_forecasts:
    raise RuntimeError("Repair requires the complete forecast-request registry.")

product_ids = registry.filtered(
    lambda row: row.record_model == "product.product"
).mapped("record_id")
registered_move_ids = set(
    registry.filtered(lambda row: row.record_model == "stock.move").mapped("record_id")
)
registered_orderpoint_ids = set(
    registry.filtered(
        lambda row: row.entity == "reordering_rule"
        and row.record_model == "stock.warehouse.orderpoint"
    ).mapped("record_id")
)
if len(registered_orderpoint_ids) != EXPECTED_ORDERPOINT_COUNT:
    raise RuntimeError(
        f"Repair requires {EXPECTED_ORDERPOINT_COUNT} registered reordering rules; "
        f"found {len(registered_orderpoint_ids)}."
    )

Orderpoint = env["stock.warehouse.orderpoint"].with_company(company).with_context(
    allowed_company_ids=[company.id], active_test=False
)
orderpoints = Orderpoint.browse(sorted(registered_orderpoint_ids)).exists()
if len(orderpoints) != EXPECTED_ORDERPOINT_COUNT:
    raise RuntimeError("One or more registered reordering rules are missing.")

all_fixture_orderpoints = Orderpoint.search(
    [("company_id", "in", [False, company.id]), ("product_id", "in", product_ids)],
    order="id",
)
if set(all_fixture_orderpoints.ids) != registered_orderpoint_ids:
    raise RuntimeError("Unexpected or missing reordering rules exist for fixture products.")

trigger_values = set(orderpoints.mapped("trigger"))
if trigger_values == {"manual"}:
    # Idempotent success is allowed only when there is no remaining generated drift.
    preexisting_manual = True
elif trigger_values == {"auto"}:
    preexisting_manual = False
else:
    raise RuntimeError(
        f"Repair refuses a partially modified trigger state: {sorted(trigger_values)!r}."
    )

open_picking_ids = registry.filtered(
    lambda row: row.entity == "open_sale_picking"
    and row.record_model == "stock.picking"
).mapped("record_id")
open_pickings = env["stock.picking"].browse(open_picking_ids).exists()
expected_move_ids = registered_move_ids | set(open_pickings.move_ids.ids)

StockMove = env["stock.move"].with_company(company).with_context(
    allowed_company_ids=[company.id], active_test=False
)
actual_moves = StockMove.search(
    [("company_id", "=", company.id), ("product_id", "in", product_ids)],
    order="id",
)
extra_moves = actual_moves.filtered(lambda move: move.id not in expected_move_ids)

if preexisting_manual and not extra_moves:
    verification = importer.run_import(env, dataset, mode="dry-run")
    print(
        json.dumps(
            {
                "status": "already-repaired",
                "database_mutations": 0,
                "dataset_version": dataset.version,
                "orderpoints_manual": len(orderpoints),
                "removed_stock_moves": 0,
                "removed_pickings": 0,
                "entry_actions": verification["entry_actions"],
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
else:
    if preexisting_manual:
        raise RuntimeError("Manual orderpoints still have unexpected stock moves; refusing cleanup.")
    if len(extra_moves) != EXPECTED_UNEXPECTED_MOVE_COUNT:
        raise RuntimeError(
            f"Repair requires exactly {EXPECTED_UNEXPECTED_MOVE_COUNT} diagnosed unexpected moves; "
            f"found {len(extra_moves)}."
        )

    orderpoints_by_name = {rule.name: rule for rule in orderpoints}
    extra_pickings = extra_moves.mapped("picking_id")
    if not extra_pickings or any(not move.picking_id for move in extra_moves):
        raise RuntimeError("Every diagnosed unexpected move must belong to an incoming picking.")

    for move in extra_moves:
        origin = move.origin or move.picking_id.origin
        rule = move.rule_id
        orderpoint = orderpoints_by_name.get(origin)
        if not orderpoint:
            raise RuntimeError(
                f"Unexpected move {move.id} is not tied to a registered reordering-rule origin."
            )
        if (
            move.state != "assigned"
            or move.company_id != company
            or move.product_id != orderpoint.product_id
            or move.location_id.usage != "supplier"
            or move.location_dest_id != orderpoint.location_id
            or move.picking_id.picking_type_code != "incoming"
            or move.procure_method != "make_to_stock"
            or not rule
            or rule.action != "pull"
            or rule.location_src_id.usage != "supplier"
            or rule.location_dest_id != orderpoint.location_id
        ):
            raise RuntimeError(
                f"Unexpected move {move.id} does not match the diagnosed scheduler-generated pattern."
            )
        if "purchase_line_id" in move._fields and move.purchase_line_id:
            raise RuntimeError(f"Unexpected move {move.id} is linked to a purchase line; refusing cleanup.")
        if move.sale_line_id:
            raise RuntimeError(f"Unexpected move {move.id} is linked to a sale line; refusing cleanup.")

    extra_ids = set(extra_moves.ids)
    for picking in extra_pickings:
        if (
            picking.company_id != company
            or picking.picking_type_code != "incoming"
            or picking.state != "assigned"
            or not picking.move_ids
            or not set(picking.move_ids.ids).issubset(extra_ids)
        ):
            raise RuntimeError(
                f"Incoming picking {picking.name} contains non-diagnosed content; refusing cleanup."
            )

    removed_move_count = len(extra_moves)
    removed_picking_count = len(extra_pickings)

    try:
        # Disable future scheduler-side replenishment first, then remove only
        # the exact still-pending artifacts produced by those auto triggers.
        orderpoints.write({"trigger": "manual"})
        extra_pickings.action_cancel()
        if any(picking.state != "cancel" for picking in extra_pickings):
            raise RuntimeError("One or more diagnosed incoming pickings did not cancel cleanly.")
        extra_pickings.unlink()
        env.flush_all()

        remaining = StockMove.search(
            [("company_id", "=", company.id), ("product_id", "in", product_ids)],
            order="id",
        )
        remaining_extra_ids = set(remaining.ids) - expected_move_ids
        if remaining_extra_ids:
            raise RuntimeError(
                f"Unexpected fixture-product stock moves remain after cleanup: "
                f"{len(remaining_extra_ids)}."
            )
        if set(orderpoints.mapped("trigger")) != {"manual"}:
            raise RuntimeError("Not all showroom reordering rules are manual after repair.")

        verification = importer.run_import(env, dataset, mode="dry-run")
        if verification["entry_actions"] != {
            "create": 0,
            "unchanged": expected_registry_count,
        }:
            raise RuntimeError("Post-repair importer verification did not return a complete no-op.")

        env.cr.commit()
    except Exception:
        env.cr.rollback()
        raise

    print(
        json.dumps(
            {
                "status": "repaired",
                "dataset_version": dataset.version,
                "orderpoints_changed_to_manual": len(orderpoints),
                "removed_stock_moves": removed_move_count,
                "removed_pickings": removed_picking_count,
                "fixture_registry_entries": expected_registry_count,
                "forecast_requests": expected_forecasts,
                "entry_actions": verification["entry_actions"],
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
