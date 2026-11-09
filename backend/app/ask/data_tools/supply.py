"""What to order (the latest order suggestion), purchase orders and their deliveries, and suppliers with
their delivery times. Read only: making or sending an order is done by a person on the Orders page."""

from datetime import timedelta

from sqlalchemy import func, select

from app.api.today import PENDING_STATUSES
from app.ask.answer_parts import Number
from app.ask.data_tools.context import PART, TEXT, TOP, Asker, ToolResult, asked_heading, branch_choice, part_choice, rows_wanted
from app.models import Branch, OrderRun, OrderSuggestion, Part, PurchaseOrder, PurchaseOrderLine, Supplier

ORDER_SUGGESTIONS_SPEC = {
    "name": "order_suggestions",
    "description": "What to order: the latest suggestion's lines, pieces, cost, reasons.",
    "parameters": {"type": "object", "properties": {**PART, "branch": TEXT, "supplier": TEXT, **TOP}},
}
PURCHASE_ORDERS_SPEC = {
    "name": "purchase_orders",
    "description": "Purchase orders and deliveries (sent = on the way).",
    "parameters": {"type": "object", "properties": {
        "status": {"enum": ["draft", "sent", "late", "received", "all"]}, "supplier": TEXT, **TOP}},
}
SUPPLIERS_SPEC = {
    "name": "suppliers",
    "description": "Suppliers, delivery days, parts, orders on the way.",
    "parameters": {"type": "object", "properties": {"name": TEXT}},
}


def order_suggestions(asker: Asker, args: dict) -> ToolResult:
    run = asker.db.scalar(select(OrderRun).where(OrderRun.organization_id == asker.organization_id)
                          .order_by(OrderRun.created_at.desc()).limit(1))
    if run is None:
        return ToolResult({"no_suggestion_yet": True, "where": "Orders page: a manager makes one"},
                          [Number(key="lines_to_order", label="Lines to order", value=0, unit="count")])
    parts = part_choice(asker, args)
    branch_id, branch = branch_choice(asker, args)
    filters = [OrderSuggestion.organization_id == asker.organization_id, OrderSuggestion.run_id == run.id,
               OrderSuggestion.status.in_(PENDING_STATUSES), parts.condition]
    if branch_id:
        filters.append(OrderSuggestion.branch_id == branch_id)
    if args.get("supplier"):
        filters.append(Supplier.name.ilike(f"%{args['supplier']}%"))
    rows = asker.db.execute(
        select(Part.name, Part.brand, Branch.name, Supplier.name, OrderSuggestion.quantity, OrderSuggestion.line_cost,
               OrderSuggestion.reason)
        .join(Part, Part.id == OrderSuggestion.part_id).join(Branch, Branch.id == OrderSuggestion.branch_id)
        .outerjoin(Supplier, Supplier.id == OrderSuggestion.supplier_id).where(*filters)
        .order_by(OrderSuggestion.quantity.desc())
    ).all()
    data = {"made_on": run.created_at.date().isoformat(), "lines": len(rows), "pieces": sum(row.quantity for row in rows)}
    if asker.sees_money:
        data["cost"] = asker.money(sum(row.line_cost or 0 for row in rows))
    data["rows"] = [{"name": f"{row[0]} ({row[1] or ''})", "branch": row[2], "supplier": row[3], "pieces": row.quantity,
                     "reason": row.reason} for row in rows[:rows_wanted(args)]]
    shown = [Number(key="lines_to_order", label="Lines to order", value=data["lines"], unit="count"),
             Number(key="pieces_to_order", label="Pieces to order", value=data["pieces"], unit="pieces")]
    shown += [Number(key="order_about", label=row["name"], about=f"{row['name']}, {row['branch']}", value=row["pieces"],
                     unit="pieces") for row in data["rows"][:8]]
    return ToolResult(data, shown, asked_heading(parts, branch))


def purchase_orders(asker: Asker, args: dict) -> ToolResult:
    status = args.get("status") or "all"
    lines = (select(PurchaseOrderLine.purchase_order_id, func.sum(PurchaseOrderLine.quantity).label("pieces"),
                    func.sum(PurchaseOrderLine.received_quantity).label("received"))
             .where(PurchaseOrderLine.organization_id == asker.organization_id)
             .group_by(PurchaseOrderLine.purchase_order_id).subquery())
    query = (select(PurchaseOrder, Supplier.name, Supplier.delivery_days, lines.c.pieces, lines.c.received)
             .join(Supplier, Supplier.id == PurchaseOrder.supplier_id).outerjoin(lines, lines.c.purchase_order_id == PurchaseOrder.id)
             .where(PurchaseOrder.organization_id == asker.organization_id).order_by(PurchaseOrder.created_at.desc()))
    if status in ("draft", "sent", "received"):
        query = query.where(PurchaseOrder.status == status)
    elif status == "late":
        query = query.where(PurchaseOrder.status == "sent")
    if args.get("supplier"):
        query = query.where(Supplier.name.ilike(f"%{args['supplier']}%"))
    rows = []
    for order, supplier, delivery_days, pieces, received in asker.db.execute(query).all():
        row = {"order": order.order_number, "supplier": supplier, "status": order.status, "pieces": int(pieces or 0)}
        if order.sent_at:
            row["sent_on"] = order.sent_at.date().isoformat()
            if order.status == "sent" and delivery_days is not None:
                expected = order.sent_at.date() + timedelta(days=delivery_days)
                row["expected_on"] = expected.isoformat()
                row["days_late"] = max(0, (asker.today - expected).days)
        if order.status == "received":
            row["received_pieces"] = int(received or 0)
        if status != "late" or row.get("days_late", 0) > 0:
            rows.append(row)
    data = {"status": status, "orders": len(rows), "rows": rows[:rows_wanted(args)]}
    shown = [Number(key="purchase_orders", label="Purchase orders", value=len(rows), unit="count")]
    shown += [Number(key="order_pieces_about", label=f"{row['order']}, {row['supplier']}", about=f"{row['order']}, {row['supplier']}",
                     value=row["pieces"], unit="pieces") for row in data["rows"][:8]]
    return ToolResult(data, shown, {"status": status})


def suppliers(asker: Asker, args: dict) -> ToolResult:
    part_count = (select(Part.supplier_id, func.count().label("parts")).where(Part.organization_id == asker.organization_id)
                  .group_by(Part.supplier_id).subquery())
    open_orders = (select(PurchaseOrder.supplier_id, func.count().label("open"))
                   .where(PurchaseOrder.organization_id == asker.organization_id, PurchaseOrder.status == "sent")
                   .group_by(PurchaseOrder.supplier_id).subquery())
    query = (select(Supplier, part_count.c.parts, open_orders.c.open)
             .outerjoin(part_count, part_count.c.supplier_id == Supplier.id)
             .outerjoin(open_orders, open_orders.c.supplier_id == Supplier.id)
             .where(Supplier.organization_id == asker.organization_id)
             .order_by(Supplier.delivery_days.desc().nulls_last(), Supplier.name))
    if args.get("name"):
        query = query.where(Supplier.name.ilike(f"%{args['name']}%"))
    rows = [{"name": supplier.name, "delivery_days": supplier.delivery_days,
             "delivery_days_from": supplier.delivery_source or "estimated", "parts": int(parts or 0),
             "orders_on_the_way": int(open_count or 0)}
            for supplier, parts, open_count in asker.db.execute(query).all()]
    data = {"suppliers": len(rows), "rows": rows[:20]}
    shown = [Number(key="delivery_days_about", label=row["name"], about=row["name"], value=row["delivery_days"], unit="days")
             for row in rows[:8] if row["delivery_days"] is not None]
    return ToolResult(data, shown, {"supplier": args["name"]} if args.get("name") else {})
