"""Will I run out? Per part and branch: the stock on the shelf, the pieces the 30-day forecast expects, and so
the days the stock lasts (like the Stock page's "runs out in N days"), compared with the supplier's delivery
time. A part is at risk when it runs out before an order placed today could arrive. Also grouped by supplier,
the most urgent first, which answers "which supplier should I order from first?"."""

from sqlalchemy import and_, func, select

from app.ask.answer_parts import Number
from app.ask.data_tools.context import PART, TEXT, TOP, Asker, ToolError, ToolResult, asked_heading, branch_choice, part_choice, rows_wanted
from app.models import Branch, Forecast, Part, StockLevel, Supplier
from app.ordering.delivery_time import DEFAULT_DELIVERY_DAYS
from app.runs_out import HORIZON_DAYS

SHOWN = 6  # rows sent to the assistant unless it asks for more (top)

SPEC = {
    "name": "running_out",
    "description": "Parts running out before a new order arrives; order_first_from = the app's most urgent supplier.",
    "parameters": {"type": "object", "properties": {**PART, "branch": TEXT, **TOP}},
}


def running_out(asker: Asker, args: dict) -> ToolResult:
    parts = part_choice(asker, args)
    branch_id, branch = branch_choice(asker, args)
    on_hand = func.coalesce(StockLevel.quantity, 0)
    delivery = func.coalesce(Supplier.delivery_days, DEFAULT_DELIVERY_DAYS)
    query = (select(Part.name, Part.brand, Branch.name.label("branch"), func.coalesce(Supplier.name, "?").label("supplier"),
                    delivery.label("delivery_days"), on_hand.label("in_stock"), Forecast.quantity.label("expected"))
             .select_from(Forecast).join(Part, Part.id == Forecast.part_id).join(Branch, Branch.id == Forecast.branch_id)
             .outerjoin(StockLevel, and_(StockLevel.part_id == Forecast.part_id, StockLevel.branch_id == Forecast.branch_id))
             .outerjoin(Supplier, Supplier.id == Part.supplier_id)
             .where(Forecast.organization_id == asker.organization_id, Forecast.horizon_days == HORIZON_DAYS,
                    Forecast.quantity > 0, Part.is_active, parts.condition))
    if branch_id:
        query = query.where(Forecast.branch_id == branch_id)
    rows = asker.db.execute(query).all()
    if not rows:
        raise ToolError("No forecast for these parts yet. Forecasts are made on the Forecasts page.")
    at_risk = []
    for row in rows:
        in_stock = max(int(row.in_stock), 0)  # below zero is a counting error on the shelf: it is empty
        days_left = in_stock * HORIZON_DAYS / row.expected
        if days_left <= row.delivery_days:
            at_risk.append({"name": f"{row.name} ({row.brand or ''})", "branch": row.branch, "in_stock": in_stock,
                            "days_left": round(days_left), "delivery_days": row.delivery_days, "supplier": row.supplier})
    at_risk.sort(key=lambda item: (item["days_left"] - item["delivery_days"], item["days_left"]))
    suppliers: dict[str, dict] = {}
    for item in at_risk:
        entry = suppliers.setdefault(item["supplier"], {"supplier": item["supplier"], "parts_at_risk": 0,
                                                        "soonest_days_left": item["days_left"], "delivery_days": item["delivery_days"]})
        entry["parts_at_risk"] += 1
        entry["soonest_days_left"] = min(entry["soonest_days_left"], item["days_left"])
    by_supplier = sorted(suppliers.values(), key=lambda entry: (entry["soonest_days_left"] - entry["delivery_days"], -entry["parts_at_risk"]))
    data = {**parts.described(), **({"branch": branch} if branch else {}), "part_branches_checked": len(rows),
            "at_risk": len(at_risk), "out_now": sum(item["in_stock"] <= 0 for item in at_risk),
            # The app's own ranking: the supplier whose parts run out longest before its delivery could arrive.
            "order_first_from": by_supplier[0]["supplier"] if by_supplier else None,
            "rows": at_risk[:rows_wanted(args) if args.get("top") else SHOWN], "by_supplier": by_supplier[:5]}
    shown = [Number(key="parts_at_risk", label="Parts that run out before an order arrives", value=len(at_risk), unit="count")]
    shown += [Number(key="days_left_about", label=f"{item['name']}, {item['branch']}", about=f"{item['name']}, {item['branch']}",
                     value=item["days_left"], unit="days") for item in at_risk[:8]]
    return ToolResult(data, shown, asked_heading(parts, branch))
