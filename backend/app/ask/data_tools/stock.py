"""Stock on the shelf now (pieces, value at cost), grouped, and only parts that are out, low or dead
(stock but no sale for N days before the last imported sale); and the days parts were out of stock."""

from datetime import date, timedelta

from sqlalchemy import and_, exists, func, not_, select

from app.ask.answer_parts import Number
from app.ask.data_tools.context import (
    CAR_NAME, DATES, PART, TEXT, TOP, TYPE_NAME, Asker, ToolResult, asked_heading, branch_choice, part_choice, period_choice, rows_wanted,
)
from app.models import Branch, Part, SaleLine, StockLevel, StockOut
from app.stock_status import DEAD_AFTER_DAYS

STOCK_GROUPS = {
    "part": Part.name + " (" + func.coalesce(Part.brand, "") + ")",
    "type": TYPE_NAME,
    "car": CAR_NAME,
    "brand": func.coalesce(Part.brand, ""),
    "category": func.coalesce(Part.category, ""),
    "branch": Branch.name,
}

STOCK_SPEC = {
    "name": "stock",
    "description": "Stock now (value at cost). only: out, low, dead (no sale for no_sale_days, default 90).",
    "parameters": {"type": "object", "properties": {
        **PART, "branch": TEXT, "group_by": {"enum": list(STOCK_GROUPS)}, **TOP,
        "only": {"enum": ["out", "low", "dead"]}, "no_sale_days": {"type": "integer"},
    }},
}
STOCK_OUTS_SPEC = {
    "name": "stock_outs",
    "description": "Past days out of stock, per part and branch.",
    "parameters": {"type": "object", "properties": {**PART, "branch": TEXT, **DATES, **TOP}},
}


def stock(asker: Asker, args: dict) -> ToolResult:
    parts = part_choice(asker, args)
    branch_id, branch = branch_choice(asker, args)
    on_hand = func.coalesce(StockLevel.quantity, 0)
    joins = StockLevel.part_id == Part.id
    if branch_id:
        joins = and_(joins, StockLevel.branch_id == branch_id)
    base = (select().select_from(Part).outerjoin(StockLevel, and_(joins, StockLevel.organization_id == asker.organization_id))
            .outerjoin(Branch, Branch.id == StockLevel.branch_id))
    filters = [Part.organization_id == asker.organization_id, Part.is_active, parts.condition]
    only = args.get("only")
    data: dict = parts.described()
    if branch:
        data["branch"] = branch
    if only in ("out", "low", "dead"):
        return _only(asker, args, only, parts, branch_id, branch, data)
    pieces = func.coalesce(func.sum(on_hand), 0)
    value = func.coalesce(func.sum(on_hand * Part.unit_cost), 0)
    total_pieces, total_value = asker.db.execute(base.add_columns(pieces, value).where(*filters)).one()
    data["total_pieces"] = int(total_pieces)
    if asker.sees_money:
        data["total_value_at_cost"] = asker.money(total_value)
    group = args.get("group_by") if args.get("group_by") in STOCK_GROUPS else None
    if group:
        key = STOCK_GROUPS[group]
        rows = asker.db.execute(
            base.add_columns(key.label("name"), pieces.label("pieces"), value.label("value")).where(*filters, key.is_not(None))
            .group_by(key).order_by((value if asker.sees_money else pieces).desc(), key).limit(rows_wanted(args))
        ).all()
        data["rows"] = [{"name": str(row.name), "pieces": int(row.pieces),
                         **({"value_at_cost": asker.money(row.value)} if asker.sees_money else {})} for row in rows]
    shown = [Number(key="pieces_in_stock", label="Pieces in stock", value=data["total_pieces"], unit="pieces")]
    if asker.sees_money:
        shown.append(Number(key="value_at_cost", label="Value at cost", value=round(total_value), unit="money"))
    shown += [Number(key="stock_about", label=row["name"], about=row["name"], value=row["pieces"], unit="pieces")
              for row in data.get("rows", [])[:8]]
    return ToolResult(data, shown, asked_heading(parts, branch))


def _only(asker: Asker, args: dict, only: str, parts, branch_id, branch: str | None, data: dict) -> ToolResult:
    """The parts that are out of stock, low, or dead, one row each (per branch when one is named)."""
    levels = select(StockLevel.part_id, func.sum(StockLevel.quantity).label("pieces")).where(
        StockLevel.organization_id == asker.organization_id)
    if branch_id:
        levels = levels.where(StockLevel.branch_id == branch_id)
    levels = levels.group_by(StockLevel.part_id).subquery()
    pieces = func.coalesce(levels.c.pieces, 0)
    filters = [Part.organization_id == asker.organization_id, Part.is_active, parts.condition]
    if only == "out":
        filters.append(pieces <= 0)
    elif only == "low":
        filters += [Part.min_stock > 0, pieces > 0, pieces <= Part.min_stock]
    else:
        days = int(args.get("no_sale_days") or DEAD_AFTER_DAYS)
        since = (asker.last_sale_day or asker.today) - timedelta(days=days - 1)
        recent = select(SaleLine.id).where(SaleLine.organization_id == asker.organization_id, SaleLine.part_id == Part.id,
                                           SaleLine.sold_on >= since)
        if branch_id:
            recent = recent.where(SaleLine.branch_id == branch_id)
        filters += [pieces > 0, not_(exists(recent))]
        data["no_sale_since"] = since.isoformat()
    query = select(Part.name, Part.brand, pieces.label("pieces"), (pieces * func.coalesce(Part.unit_cost, 0)).label("value")) \
        .outerjoin(levels, levels.c.part_id == Part.id).where(*filters)
    rows = asker.db.execute(query.order_by(pieces.desc(), Part.name)).all()
    data.update({"only": only, "total_parts": len(rows), "total_pieces": sum(int(row.pieces) for row in rows)})
    if asker.sees_money:
        data["total_value_at_cost"] = asker.money(sum(int(row.value) for row in rows))
    data["rows"] = [{"name": f"{row.name} ({row.brand or ''})", "pieces": int(row.pieces)} for row in rows[:rows_wanted(args)]]
    shown = [Number(key=f"{only}_parts", label=f"Parts {only}", value=data["total_parts"], unit="count"),
             Number(key="pieces_in_stock", label="Pieces in stock", value=data["total_pieces"], unit="pieces")]
    shown += [Number(key="stock_about", label=row["name"], about=row["name"], value=row["pieces"], unit="pieces")
              for row in data["rows"][:8]]
    return ToolResult(data, shown, {**asked_heading(parts, branch), "only": only})


def days_out(asker: Asker, part_condition, branch_id, first: date, last: date) -> int:
    """Days out of stock in a period, added up over the parts (and branches) chosen."""
    days = func.least(StockOut.last_day, last) - func.greatest(StockOut.first_day, first) + 1
    query = (select(func.coalesce(func.sum(days), 0)).select_from(StockOut).join(Part, Part.id == StockOut.part_id)
             .where(StockOut.organization_id == asker.organization_id, StockOut.first_day <= last,
                    StockOut.last_day >= first, part_condition))
    if branch_id:
        query = query.where(StockOut.branch_id == branch_id)
    return int(asker.db.scalar(query))


def stock_outs(asker: Asker, args: dict) -> ToolResult:
    parts = part_choice(asker, args)
    branch_id, branch = branch_choice(asker, args)
    first, last = period_choice(asker, args)
    days = (func.least(StockOut.last_day, last) - func.greatest(StockOut.first_day, first) + 1)
    filters = [StockOut.organization_id == asker.organization_id, StockOut.first_day <= last, StockOut.last_day >= first,
               parts.condition]
    if branch_id:
        filters.append(StockOut.branch_id == branch_id)
    query = (select(Part.name, Part.brand, Branch.name.label("branch"), func.sum(days).label("days"))
             .join(Part, Part.id == StockOut.part_id).join(Branch, Branch.id == StockOut.branch_id).where(*filters)
             .group_by(Part.name, Part.brand, Branch.name))
    rows = asker.db.execute(query.order_by(func.sum(days).desc(), Part.name)).all()
    data = {"period": [first.isoformat(), last.isoformat()], **parts.described(),
            "part_branches_out": len(rows), "days_out_total": sum(int(row.days) for row in rows),
            "rows": [{"name": f"{row.name} ({row.brand or ''})", "branch": row.branch, "days_out": int(row.days)}
                     for row in rows[:rows_wanted(args)]]}
    if branch:
        data["branch"] = branch
    shown = [Number(key="days_out_of_stock", label="Days out of stock", value=data["days_out_total"], unit="days")]
    shown += [Number(key="days_out_about", label=f"{row['name']}, {row['branch']}", about=f"{row['name']}, {row['branch']}",
                     value=row["days_out"], unit="days") for row in data["rows"][:8]]
    return ToolResult(data, shown, asked_heading(parts, branch, first, last))
