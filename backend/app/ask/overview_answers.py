"""Answers about the whole shop: today's briefing, and branches compared with each other."""

from datetime import date

from sqlalchemy import func, select

from app.alerts.problem import NEEDS_ACTION, WORTH_A_LOOK, pieces
from app.api.today import BASELINE_WEEKS, find_late_deliveries, open_alert_group, to_order_summary, weekly_sales
from app.ask.answer_parts import Answer, Asked, Number, date_range, part_not_found, pick_parts, range_words
from app.ask.periods import LABELS, day_range, period_used, range_before
from app.ask.question import BRANCHES_JOINED, Question
from app.ask.sales_answers import pieces_and_value
from app.ask.stock_answers import running_out
from app.models import Branch, Part, SaleLine
from app.runs_out import RUNNING_OUT_WITHIN_DAYS


WEEK_PERIODS = ("today", "this_week")  # "what's going on today?": this week against a normal week


def percent_change(now: int, before: int) -> int | None:
    return None if before == 0 else round(100 * (now - before) / before)


def change_words(percent: int | None) -> str:
    if percent is None:
        return "no sales before"
    return "the same" if percent == 0 else f"{'up' if percent > 0 else 'down'} {abs(percent)}%"


def today_briefing(asked: Asked) -> Answer:
    db, shop = asked.db, asked.organization_id
    weekly = weekly_sales(db, shop)
    needs_action, needs_action_total = open_alert_group(db, shop, NEEDS_ACTION, asked.currency)
    worth_a_look, worth_a_look_total = open_alert_group(db, shop, WORTH_A_LOOK, asked.currency)
    to_order = to_order_summary(db, shop, asked.currency is not None)
    late = find_late_deliveries(db, shop, date.today())
    running = running_out(Asked(db, shop, Question("running_out"), asked.today, asked.currency)).values.get("count", 0)

    def alerts(found) -> list[dict]:
        return [{"part": alert.part_name, "branch": alert.branch_name, "what": alert.sentence} for alert in found]

    values: dict = {
        "day": asked.today.isoformat(),
        "needs_action": {"count": needs_action_total, "top": alerts(needs_action)},
        "worth_a_look": {"count": worth_a_look_total, "top": alerts(worth_a_look)},
        "to_order": {"lines": to_order.lines if to_order else 0, **asked.money_value(getattr(to_order, "total_cost", 0))},
        "late_deliveries": {
            "count": len(late),
            "top": [{"order_number": d.order_number, "supplier": d.supplier_name, "days_late": d.days_late} for d in late[:3]],
        },
        "running_out": {"count": running, "within_days": RUNNING_OUT_WITHIN_DAYS},
    }
    numbers = []
    sales_words = "No sales yet."
    if asked.question.period not in (None, *WEEK_PERIODS):
        values["sales_in_period"], numbers, sales_words = _period_sales(asked)
    elif weekly:
        first = weekly.weeks[-1].week_start
        percent = percent_change(weekly.this_week, weekly.normal)
        values["sales_this_week"] = {
            "pieces": weekly.this_week, "normal_week": weekly.normal, "percent_vs_normal": percent,
            "range": date_range(first, asked.today), "normal_week_is_average_of_weeks": BASELINE_WEEKS,
            "top_parts": [{"name": top.name, "sku": top.sku, "pieces": top.quantity} for top in weekly.top_parts[:3]],
        }
        sales_words = (
            f"This week ({range_words(first, asked.today)}): {pieces(weekly.this_week)} sold, "
            f"{change_words(percent)} on a normal week ({pieces(weekly.normal)})."
        )
        numbers += [
            Number(key="pieces_this_week", label="Pieces sold this week", value=weekly.this_week, unit="pieces"),
            Number(key="normal_week", label="A normal week", value=weekly.normal, unit="pieces"),
        ]
    numbers += [
        Number(key="needs_action", label="Alerts that need action", value=needs_action_total, unit="count"),
        Number(key="worth_a_look", label="Worth a look", value=worth_a_look_total, unit="count"),
        Number(key="lines_to_order", label="Lines to order", value=values["to_order"]["lines"], unit="count"),
        *asked.money_number("total_cost", "Total cost", getattr(to_order, "total_cost", 0)),
        Number(key="late_deliveries", label="Late deliveries", value=len(late), unit="count"),
        Number(key="parts_running_out", label="Parts running out", value=running, unit="count"),
    ]
    return Answer(
        "today_briefing",
        values,
        f"{sales_words} {needs_action_total} alerts need action, {worth_a_look_total} are worth a look. "
        f"To order: {values['to_order']['lines']} lines. Late deliveries: {len(late)}. "
        f"Running out within {RUNNING_OUT_WITHIN_DAYS} days: {running} parts.",
        numbers,
    )


def _period_sales(asked: Asked) -> tuple[dict, list[Number], str]:
    """The briefing's sales for the period asked about, against the period before it."""
    period = asked.question.period
    first, last = day_range(period, asked.today)
    before_first, before_last = range_before(period, asked.today)
    everything = pick_parts(asked)
    now, _ = pieces_and_value(asked, everything, None, first, last)
    before, _ = pieces_and_value(asked, everything, None, before_first, before_last)
    percent = percent_change(now, before)
    values = {"period": period, "range": date_range(first, last), "pieces": now, "before_range": date_range(before_first, before_last),
              "before_pieces": before, "percent": percent}
    numbers = [
        Number(key="pieces_now", label="Pieces sold, this period", value=now, unit="pieces"),
        Number(key="pieces_before", label="Pieces sold, period before", value=before, unit="pieces"),
        Number(key="this_period", label="This period", value=date_range(first, last), unit="date_range"),
        Number(key="period_before", label="Period before", value=date_range(before_first, before_last), unit="date_range"),
    ]
    words = (f"{LABELS[period].capitalize()} ({range_words(first, last)}): {pieces(now)} sold, "
             f"{change_words(percent)} on {range_words(before_first, before_last)} ({pieces(before)}).")
    return values, numbers, words


def compare_branches(asked: Asked) -> Answer:
    parts = pick_parts(asked)
    if parts is None:
        return part_not_found(asked)
    period = period_used("compare_branches", asked.question.period)
    first, last = day_range(period, asked.today)
    before_first, before_last = range_before(period, asked.today)
    now = _pieces_per_branch(asked, parts.condition, first, last)
    before = _pieces_per_branch(asked, parts.condition, before_first, before_last)
    names = asked.db.scalars(select(Branch.name).where(Branch.organization_id == asked.organization_id))
    if asked.question.branches:  # "compare Casablanca and Rabat": only the branches asked about
        names = [name for name in names if name in asked.question.branches.split(BRANCHES_JOINED)]
    rows = sorted(
        (
            {"branch": name, "pieces": now.get(name, (0, 0))[0], "pieces_before": before.get(name, (0, 0))[0],
             "percent_change": percent_change(now.get(name, (0, 0))[0], before.get(name, (0, 0))[0]),
             **asked.money_value(now.get(name, (0, 0))[1])}
            for name in names
        ),
        key=lambda row: (-row["pieces"], row["branch"]),
    )
    total = sum(row["pieces"] for row in rows)
    each = ", ".join(f"{row['branch']} {pieces(row['pieces'])} ({change_words(row['percent_change'])})" for row in rows)
    return Answer(
        "compare_branches",
        {"subject": parts.subject, "period": period, "range": date_range(first, last),
         "before_range": date_range(before_first, before_last), "total_pieces": total, "branches": rows,
         "only_asked": bool(asked.question.branches)},
        f"Sales of {parts.label}, {LABELS[period]} ({range_words(first, last)}), most sold first: {each}. "
        f"Compared with {range_words(before_first, before_last)}.",
        [Number(label=row["branch"], value=row["pieces"], unit="pieces") for row in rows]
        + [Number(key="this_period", label="This period", value=date_range(first, last), unit="date_range"),
           Number(key="period_before", label="Period before", value=date_range(before_first, before_last), unit="date_range")],
    )


def _pieces_per_branch(asked: Asked, condition, first: date, last: date) -> dict[str, tuple[int, int]]:
    """Branch name -> (pieces sold, sales value in centimes)."""
    rows = asked.db.execute(
        select(Branch.name, func.sum(SaleLine.quantity), func.coalesce(func.sum(SaleLine.quantity * SaleLine.unit_price), 0))
        .join(Branch, Branch.id == SaleLine.branch_id)
        .join(Part, Part.id == SaleLine.part_id)
        .where(SaleLine.organization_id == asked.organization_id, SaleLine.sold_on.between(first, last), condition)
        .group_by(Branch.name)
    )
    return {name: (int(quantity), int(value)) for name, quantity, value in rows}
