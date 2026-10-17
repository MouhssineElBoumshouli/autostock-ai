"""Read-only diagnosis for Moroccan showroom drift after import."""

from __future__ import annotations

import json


company = env.ref("base.main_company")
registry = env["autostock.morocco.fixture"].search([], order="fixture_key, id")
product_ids = registry.filtered(
    lambda row: row.record_model == "product.product"
).mapped("record_id")
registered_move_ids = set(
    registry.filtered(lambda row: row.record_model == "stock.move").mapped("record_id")
)
open_picking_ids = registry.filtered(
    lambda row: row.entity == "open_sale_picking" and row.record_model == "stock.picking"
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


def grouped(records, getter):
    result = {}
    for record in records:
        key = str(getter(record) or "(empty)")
        result[key] = result.get(key, 0) + 1
    return dict(sorted(result.items()))


has_purchase_line = "purchase_line_id" in StockMove._fields
purchase_moves = extra_moves.filtered(
    lambda move: has_purchase_line and bool(move.purchase_line_id)
) if has_purchase_line else StockMove.browse()

orderpoints = env["stock.warehouse.orderpoint"].with_company(company).with_context(
    allowed_company_ids=[company.id], active_test=False
).search(
    [("company_id", "in", [False, company.id]), ("product_id", "in", product_ids)],
    order="id",
)
orderpoint_triggers = (
    grouped(orderpoints, lambda row: row.trigger)
    if "trigger" in orderpoints._fields
    else {"(trigger field unavailable)": len(orderpoints)}
)

purchase_model_available = (
    "purchase.order" in env.registry.models
    and "purchase.order.line" in env.registry.models
)
purchase_orders = []
if purchase_model_available:
    purchase_lines = env["purchase.order.line"].with_company(company).with_context(
        allowed_company_ids=[company.id], active_test=False
    ).search([("company_id", "=", company.id), ("product_id", "in", product_ids)])
    purchase_orders = purchase_lines.mapped("order_id")

has_rule = "rule_id" in StockMove._fields
rule_summary = {}
if has_rule:
    for move in extra_moves:
        rule = move.rule_id
        if not rule:
            key = "(no rule)"
        else:
            action = getattr(rule, "action", False) or "(no action)"
            route = getattr(getattr(rule, "route_id", False), "display_name", False) or "(no route)"
            key = f"{rule.display_name} | action={action} | route={route}"
        rule_summary[key] = rule_summary.get(key, 0) + 1
    rule_summary = dict(sorted(rule_summary.items()))

installed_modules = sorted(
    env["ir.module.module"].search([("state", "=", "installed")]).mapped("name")
)

samples = []
for move in extra_moves[:25]:
    purchase_line = move.purchase_line_id if has_purchase_line else False
    purchase_order = purchase_line.order_id if purchase_line else False
    samples.append(
        {
            "id": move.id,
            "sku": move.product_id.default_code,
            "state": move.state,
            "quantity": move.product_uom_qty,
            "origin": move.origin or (move.picking_id.origin if move.picking_id else False),
            "picking": move.picking_id.name if move.picking_id else False,
            "picking_type": move.picking_id.picking_type_code if move.picking_id else False,
            "source_usage": move.location_id.usage,
            "destination_usage": move.location_dest_id.usage,
            "procure_method": move.procure_method,
            "purchase_order": purchase_order.name if purchase_order else False,
            "purchase_order_state": purchase_order.state if purchase_order else False,
            "created_at": str(move.create_date or ""),
            "scheduled_date": str(move.date or ""),
        }
    )

report = {
    "status": "diagnostic-only",
    "database_mutations": 0,
    "dataset_version": company.autostock_demo_dataset_version,
    "fixture_registry_entries": len(registry),
    "fixture_products": len(product_ids),
    "registered_stock_moves": len(registered_move_ids),
    "expected_open_sale_moves": len(set(open_pickings.move_ids.ids)),
    "actual_fixture_product_moves": len(actual_moves),
    "unexpected_stock_moves": len(extra_moves),
    "unexpected_by_state": grouped(extra_moves, lambda move: move.state),
    "unexpected_by_picking_type": grouped(
        extra_moves,
        lambda move: move.picking_id.picking_type_code if move.picking_id else "no_picking",
    ),
    "unexpected_by_source_destination": grouped(
        extra_moves, lambda move: f"{move.location_id.usage}->{move.location_dest_id.usage}"
    ),
    "unexpected_with_purchase_line": len(purchase_moves),
    "purchase_model_available": purchase_model_available,
    "unexpected_by_stock_rule": rule_summary,
    "installed_modules": installed_modules,
    "orderpoints": len(orderpoints),
    "orderpoints_by_trigger": orderpoint_triggers,
    "purchase_orders": len(purchase_orders),
    "purchase_orders_by_state": (
        grouped(purchase_orders, lambda order: order.state)
        if purchase_model_available
        else {"(purchase module not installed)": 0}
    ),
    "unexpected_move_samples": samples,
}

print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
