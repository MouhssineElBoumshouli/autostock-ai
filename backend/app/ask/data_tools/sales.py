"""Sales over any period: pieces, value and margin (money only for those who see it), grouped by part,
type, car, brand, category, branch, day, week or month, the biggest first, optionally compared with the
period just before or the same dates last year. Every total and % change is computed here."""

from datetime import date, timedelta

from sqlalchemy import Date, cast, func, select

from app.ask.answer_parts import Number
from app.ask.data_tools.stock import days_out
from app.ask.data_tools.context import (
    CAR_NAME, DATES, PART, TEXT, TOP, TYPE_NAME, Asker, ToolResult, asked_heading, branch_choice, part_choice, percent_change, period_choice,
    rows_wanted,
)
from app.models import Branch, Part, SaleLine

GROUPS = {
    "part": (Part.name + " (" + func.coalesce(Part.brand, "") + ")"),
    "type": TYPE_NAME,
    "car": CAR_NAME,
    "brand": func.coalesce(Part.brand, ""),
    "category": func.coalesce(Part.category, ""),
    "branch": Branch.name,
    "day": cast(SaleLine.sold_on, Date),
    "week": cast(func.date_trunc("week", SaleLine.sold_on), Date),
    "month": cast(func.date_trunc("month", SaleLine.sold_on), Date),
}
TIME_GROUPS = ("day", "week", "month")

SPEC = {
    "name": "sales",
    "description": "Pieces sold (value, margin) in a period; group_by gives rows, most first.",
    "parameters": {"type": "object", "properties": {
        **PART, "branch": TEXT, **DATES, "group_by": {"enum": list(GROUPS)}, **TOP,
        "compare": {"enum": ["previous_period", "last_year"]},
    }},
}


def sales(asker: Asker, args: dict) -> ToolResult:
    parts = part_choice(asker, args)
    branch_id, branch = branch_choice(asker, args)
    first, last = period_choice(asker, args)
    asked_period = [first.isoformat(), last.isoformat()]
    if asker.last_sale_day and first <= asker.last_sale_day < last:
        last = asker.last_sale_day  # days not imported yet would make every comparison look like a drop
    group = args.get("group_by") if args.get("group_by") in GROUPS else None
    now = _totals(asker, parts.condition, branch_id, first, last, group, rows_wanted(args))
    data = {"period": [first.isoformat(), last.isoformat()], **({"branch": branch} if branch else {}),
            **parts.described(), **now["total"]}
    if asker.last_sale_day and asked_period[1] > asker.last_sale_day.isoformat():
        data["note"] = (f"sales imported up to {asker.last_sale_day.isoformat()} only: period asked "
                        f"{asked_period[0]} to {asked_period[1]}, counted up to {last.isoformat()}")
    compare = args.get("compare")
    if compare in ("previous_period", "last_year"):
        before_first, before_last = _before(first, last, compare)
        before = _totals(asker, parts.condition, branch_id, before_first, before_last, group, None)
        data["compared_with"] = _compared(asker, now["total"], before["total"], before_first, before_last)
        # What may explain the change, in the same answer: days out of stock and the price in both periods,
        # and (for the period before) the same dates last year, for the season.
        data["stock_out_days"] = days_out(asker, parts.condition, branch_id, first, last)
        data["compared_with"]["stock_out_days"] = days_out(asker, parts.condition, branch_id, before_first, before_last)
        if compare == "previous_period":
            year_first, year_last = _before(first, last, "last_year")
            last_year = _totals(asker, parts.condition, branch_id, year_first, year_last, None, None)["total"]
            data["same_dates_last_year"] = _compared(asker, now["total"], last_year, year_first, year_last)
        for row in now["rows"]:
            earlier = before["by_name"].get(row["name"], 0) if group not in TIME_GROUPS else None
            if earlier is not None:
                row["before"] = earlier
                row["change_percent"] = percent_change(row["pieces"], earlier)
    if group:
        data["rows"] = now["rows"]
    heading = {**asked_heading(parts, branch, first, last), **({"group_by": group} if group else {}),
               **({"compare": compare} if compare in ("previous_period", "last_year") else {})}
    return ToolResult(data, _shown(data), heading)


def _compared(asker: Asker, now: dict, before: dict, first: date, last: date) -> dict:
    compared = {"period": [first.isoformat(), last.isoformat()], **before,
                "change_pieces": now["pieces"] - before["pieces"], "change_percent": percent_change(now["pieces"], before["pieces"])}
    if asker.sees_money and now.get("value") and before.get("value"):
        compared["average_price"] = round(before["value"] / before["pieces"], 2)
        now["average_price"] = round(now["value"] / now["pieces"], 2)
    return compared


def _before(first: date, last: date, compare: str) -> tuple[date, date]:
    if compare == "last_year":
        return _year_earlier(first), _year_earlier(last)
    length = (last - first).days + 1
    return first - timedelta(days=length), first - timedelta(days=1)


def _year_earlier(day: date) -> date:
    return day.replace(year=day.year - 1) if not (day.month == 2 and day.day == 29) else day.replace(year=day.year - 1, day=28)


def _totals(asker: Asker, part_condition, branch_id, first: date, last: date, group: str | None, top: int | None) -> dict:
    pieces = func.coalesce(func.sum(SaleLine.quantity), 0)
    value = func.coalesce(func.sum(SaleLine.quantity * SaleLine.unit_price), 0)
    cost = func.coalesce(func.sum(SaleLine.quantity * Part.unit_cost), 0)
    filters = [SaleLine.organization_id == asker.organization_id, SaleLine.sold_on.between(first, last), part_condition]
    if branch_id:
        filters.append(SaleLine.branch_id == branch_id)
    base = select().select_from(SaleLine).join(Part, Part.id == SaleLine.part_id).join(Branch, Branch.id == SaleLine.branch_id)
    total_pieces, total_value, total_cost = asker.db.execute(base.add_columns(pieces, value, cost).where(*filters)).one()
    result = {"total": _money_fields(asker, {"pieces": int(total_pieces)}, total_value, total_cost), "rows": [], "by_name": {}}
    if group:
        key = GROUPS[group]
        query = base.add_columns(key.label("name"), pieces.label("pieces"), value, cost).where(*filters).group_by(key)
        query = query.order_by(key) if group in TIME_GROUPS else query.order_by(pieces.desc(), key)
        rows = asker.db.execute(query).all()
        result["by_name"] = {str(row.name): int(row.pieces) for row in rows}
        shown_rows = rows if group in TIME_GROUPS else rows[:top] if top else rows
        result["rows"] = [_money_fields(asker, {"name": str(row.name), "pieces": int(row.pieces)}, row[2], row[3]) for row in shown_rows]
    return result


def _money_fields(asker: Asker, fields: dict, value, cost) -> dict:
    if asker.sees_money and value:
        fields["value"] = asker.money(value)
        fields["margin"] = asker.money(value - cost)
        fields["margin_percent"] = round((value - cost) * 100 / value) if value else None
    return fields


def _shown(data: dict) -> list[Number]:
    shown = [Number(key="pieces_sold", label="Pieces sold", value=data["pieces"], unit="pieces")]
    if "value" in data:
        shown.append(Number(key="sales_value", label="Sales value", value=round(data["value"] * 100), unit="money"))
    if "compared_with" in data:
        before = data["compared_with"]
        shown.append(Number(key="pieces_sold_before", label="Pieces sold, period compared",
                            value=before["pieces"], unit="pieces", about="/".join(before["period"])))
    for row in data.get("rows", [])[:8]:
        shown.append(Number(key="sold_about", label=row["name"], about=row["name"], value=row["pieces"], unit="pieces"))
    return shown
