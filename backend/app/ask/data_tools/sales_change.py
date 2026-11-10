"""Why did sales change? The period compared with the period just before, and the app's own rule-based reasons
(app/ask/why.py): more or fewer days out of stock, the average price, the same dates last year (the season),
an open alert pointing the same way. The model only says these reasons; it never finds its own."""

from sqlalchemy import select

from app.ask.answer_parts import Number
from app.ask.data_tools.context import DATES, PART, TEXT, Asker, ToolResult, asked_heading, branch_choice, part_choice, percent_change, period_choice
from app.ask.data_tools.sales import _before, _totals
from app.ask.data_tools.stock import days_out
from app.ask.why import LAST_YEAR, MAIN_REASON, SalesFacts, direction, last_year_compared, reasons
from app.models import Alert, Branch, Part

SPEC = {
    "name": "why_sales",
    "description": "Why sales went up or down, with the app's reasons.",
    "parameters": {"type": "object", "properties": {**PART, "branch": TEXT, **DATES}},
}


def why_sales(asker: Asker, args: dict) -> ToolResult:
    parts = part_choice(asker, args)
    branch_id, branch = branch_choice(asker, args)
    first, last = period_choice(asker, args)
    if asker.last_sale_day and first <= asker.last_sale_day < last:
        last = asker.last_sale_day
    before_first, before_last = _before(first, last, "previous_period")
    year_first, year_last = _before(first, last, "last_year")
    now = _totals(asker, parts.condition, branch_id, first, last, None, None)["total"]
    before = _totals(asker, parts.condition, branch_id, before_first, before_last, None, None)["total"]
    last_year = _totals(asker, parts.condition, branch_id, year_first, year_last, None, None)["total"]
    facts = SalesFacts(
        now=now["total_pieces"], before=before["total_pieces"], last_year=last_year["total_pieces"],
        out_now=days_out(asker, parts.condition, branch_id, first, last),
        out_before=days_out(asker, parts.condition, branch_id, before_first, before_last),
        price_now=_price(now), price_before=_price(before), alerts=_alerts(asker, parts.condition, branch_id),
    )
    found = reasons(facts)
    way = direction(facts.now, facts.before)
    data = {
        **parts.described(), **({"branch": branch} if branch else {}),
        "period": [first.isoformat(), last.isoformat()], "pieces": facts.now,
        "period_before": [before_first.isoformat(), before_last.isoformat()], "pieces_before": facts.before,
        "change_pieces": facts.now - facts.before, "change_percent": percent_change(facts.now, facts.before), "direction": way,
        "same_dates_last_year": facts.last_year, "days_out_of_stock": facts.out_now, "days_out_of_stock_before": facts.out_before,
        "reasons_found": [_said(asker, reason) for reason in found] or ["no rule explains it (not stock, price, season or an alert)"],
    }
    if (compared := last_year_compared(facts.now, facts.last_year)) and way != "same":
        data["last_year"] = LAST_YEAR[compared]
    if asker.sees_money and facts.price_now and facts.price_before:
        data["average_price"], data["average_price_before"] = asker.money(facts.price_now), asker.money(facts.price_before)
    shown = [Number(key="pieces_now", label="Pieces sold, this period", value=facts.now, unit="pieces"),
             Number(key="pieces_before", label="Pieces sold, period before", value=facts.before, unit="pieces"),
             Number(key="same_days_last_year", label="Same days last year", value=facts.last_year, unit="pieces"),
             Number(key="days_out_of_stock_now", label="Days out of stock, this period", value=facts.out_now, unit="days"),
             Number(key="days_out_of_stock_before", label="Days out of stock, period before", value=facts.out_before, unit="days")]
    return ToolResult(data, shown, asked_heading(parts, branch, first, last))


def _price(total: dict) -> int | None:
    """Average selling price in centimes (SalesFacts' unit), from the total in the shop's currency."""
    if not total.get("total_value") or not total["total_pieces"]:
        return None
    return round(total["total_value"] * 100 / total["total_pieces"])


def _alerts(asker: Asker, part_condition, branch_id) -> tuple[dict, ...]:
    query = (select(Alert.kind, Branch.name).join(Part, Part.id == Alert.part_id).join(Branch, Branch.id == Alert.branch_id)
             .where(Alert.organization_id == asker.organization_id, Alert.status == "open", part_condition))
    if branch_id:
        query = query.where(Alert.branch_id == branch_id)
    return tuple({"kind": kind, "branch": name} for kind, name in asker.db.execute(query).all())


def _said(asker: Asker, reason: dict) -> str:
    """One reason in plain words, with its numbers (prices only for people who see money)."""
    words = MAIN_REASON[reason["kind"]]
    if reason["kind"] in ("out_of_stock", "back_in_stock"):
        return f"{words} ({reason['days_now']} days vs {reason['days_before']})"
    if reason["kind"] in ("price_up", "price_down"):
        return f"{words} ({reason['percent']} %)" if asker.sees_money else words
    if reason["kind"] == "season":
        return f"{words} ({reason['last_year']} pieces last year)"
    return f"{words} ({reason['alert_kind']} alert, {reason['branch']})"
