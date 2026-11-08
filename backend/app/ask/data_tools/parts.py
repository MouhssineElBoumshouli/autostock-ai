"""Finding parts (what the shop has under a type, car, brand or part number), and their prices,
costs and margins (only for people who see money)."""

from sqlalchemy import func, select

from app.ask.answer_parts import Number
from app.ask.data_tools.context import CAR_NAME, PART, TEXT, TOP, TYPE_NAME, Asker, ToolResult, asked_heading, part_choice, rows_wanted
from app.models import Part

PART_PARAMS = {**PART, "oem": TEXT, "category": TEXT}
FIND_PARTS_SPEC = {
    "name": "find_parts",
    "description": "Which parts the shop has: count, types, cars, brands, examples.",
    "parameters": {"type": "object", "properties": {**PART_PARAMS, **TOP}},
}
PRICES_SPEC = {
    "name": "prices",
    "description": "Sale price, cost, margin per part.",
    "parameters": {"type": "object", "properties": {**PART_PARAMS, **TOP}},
}


def find_parts(asker: Asker, args: dict) -> ToolResult:
    parts = part_choice(asker, args)
    where = [Part.organization_id == asker.organization_id, parts.condition]

    def distinct(column) -> list[str]:
        return sorted(value for value in asker.db.scalars(select(column).where(*where).distinct()) if value)[:12]

    examples = asker.db.execute(select(Part.name, Part.brand, Part.oem_reference, Part.sku).where(*where)
                                .order_by(Part.name, Part.brand).limit(rows_wanted(args))).all()
    data = {"parts": parts.matched, "types": distinct(TYPE_NAME), "cars": distinct(CAR_NAME), "brands": distinct(Part.brand),
            "examples": [{"name": name, "brand": brand, "oem": oem, "sku": sku} for name, brand, oem, sku in examples]}
    return ToolResult(data, [Number(key="matching_parts", label="Matching parts", value=parts.matched, unit="count")],
                      asked_heading(parts, None))


def prices(asker: Asker, args: dict) -> ToolResult:
    parts = part_choice(asker, args)
    rows = asker.db.execute(select(Part.name, Part.brand, Part.sale_price, Part.unit_cost)
                            .where(Part.organization_id == asker.organization_id, parts.condition)
                            .order_by(Part.name, Part.brand).limit(rows_wanted(args))).all()
    data = {"parts": parts.matched, "rows": [
        {"name": f"{name} ({brand or ''})", "sale_price": asker.money(price), "cost": asker.money(cost),
         "margin_percent": round((price - cost) * 100 / price) if price and cost is not None else None}
        for name, brand, price, cost in rows]}
    shown = [Number(key="sale_price_about", label=f"{name} ({brand or ''})", about=f"{name} ({brand or ''})", value=price,
                    unit="money") for name, brand, price, _ in rows[:8] if price is not None]
    return ToolResult(data, shown, asked_heading(parts, None))
