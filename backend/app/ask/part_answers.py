"""Answers about one part (or the parts a word matches): why its sales changed, and everything about it."""

import uuid
from datetime import date, timedelta

from sqlalchemy import func, select

from app.alerts.problem import pieces
from app.ask.answer_parts import (
    SHOWN_ROWS, Answer, Asked, Number, branch_id, date_range, part_not_found, pick_parts, range_words, where_words,
    which_part,
)
from app.ask.overview_answers import change_words, percent_change
from app.ask.periods import LABELS, day_range, period_used, range_before, same_day_year_before
from app.ask.sales_answers import pieces_and_value
from app.ask.why import SalesFacts, direction, reasons
from app.models import Alert, Branch, Forecast, Part, SaleLine, StockLevel, StockOut
from app.runs_out import HORIZON_DAYS

WEEKS_SHOWN = 8
RECENT_DAYS = 30


def explain_part_change(asked: Asked) -> Answer:
    """Why sales changed: now vs before vs last year, days out of stock, prices and open alerts, read by
    rules into reasons, the main one first (app/ask/why.py). Stock now and the forecast are given too."""
    if not asked.question.part:
        return which_part("which_part_forecast", "why are brake pad sales down")
    parts = pick_parts(asked)
    if parts is None:
        return part_not_found(asked)
    period = period_used("explain_part_change", asked.question.period)
    first, last = day_range(period, asked.today)
    before_first, before_last = range_before(period, asked.today)
    shop_branch = branch_id(asked)
    now, _ = pieces_and_value(asked, parts, shop_branch, first, last)
    before, _ = pieces_and_value(asked, parts, shop_branch, before_first, before_last)
    last_year, _ = pieces_and_value(asked, parts, shop_branch, same_day_year_before(first), same_day_year_before(last))
    weekly = []
    for week in range(WEEKS_SHOWN - 1, -1, -1):
        week_last = asked.today - timedelta(days=7 * week)
        week_first = week_last - timedelta(days=6)
        weekly.append({"week": date_range(week_first, week_last), "pieces": pieces_and_value(asked, parts, shop_branch, week_first, week_last)[0]})
    out_now = _days_out_of_stock(asked, parts.condition, shop_branch, first, last)
    out_before = _days_out_of_stock(asked, parts.condition, shop_branch, before_first, before_last)
    alerts = _open_alerts(asked, parts.condition, shop_branch)
    in_stock = _stock(asked, parts.condition, shop_branch)
    expected = _forecast(asked, parts.condition, shop_branch)
    percent = percent_change(now, before)
    found = reasons(SalesFacts(
        now, before, last_year, out_now, out_before,
        _average_price(asked, parts.condition, shop_branch, first, last),
        _average_price(asked, parts.condition, shop_branch, before_first, before_last), tuple(alerts),
    ))
    if not asked.currency:  # people who don't see money get the price change, not the prices
        found = [{k: v for k, v in reason.items() if not k.startswith("price_")} for reason in found]
    return Answer(
        "explain_part_change",
        {"subject": parts.subject, **asked.place(), "period": period, "range": date_range(first, last),
         "before_range": date_range(before_first, before_last), "pieces_now": now, "pieces_before": before,
         "percent_change": percent, "direction": direction(now, before), "reasons": found,
         "same_days_last_year": last_year, "weekly_pieces": weekly,
         "days_out_of_stock_now": out_now, "days_out_of_stock_before": out_before,
         "days_out_of_stock_counts": _days_counted_over(parts.part_ids, shop_branch), "stock_now": in_stock,
         "expected_next_30_days": expected, "open_alerts": alerts},
        f"{parts.title}{where_words(asked)}, {LABELS[period]} ({range_words(first, last)}): {pieces(now)}, "
        f"{change_words(percent)} on {range_words(before_first, before_last)} ({pieces(before)}). "
        f"Same days last year: {pieces(last_year)}. Days out of stock (per branch): {out_now} now, {out_before} before. "
        f"In stock now: {pieces(in_stock)}. Expected next {HORIZON_DAYS} days: {pieces(expected)}. Open alerts: {len(alerts)}.",
        [
            Number(key="pieces_now", label="Pieces sold, this period", value=now, unit="pieces"),
            Number(key="pieces_before", label="Pieces sold, period before", value=before, unit="pieces"),
            Number(key="same_days_last_year", label="Same days last year", value=last_year, unit="pieces"),
            Number(key="days_out_of_stock_now", label="Days out of stock, this period", value=out_now, unit="days"),
            Number(key="days_out_of_stock_before", label="Days out of stock, period before", value=out_before, unit="days"),
            Number(key="in_stock", label="In stock now", value=in_stock, unit="pieces"),
            Number(key="expected_next_30_days", label="Expected, next 30 days", value=expected, unit="pieces"),
            Number(key="open_alerts", label="Open alerts", value=len(alerts), unit="count"),
            Number(key="this_period", label="This period", value=date_range(first, last), unit="date_range"),
            Number(key="period_before", label="Period before", value=date_range(before_first, before_last), unit="date_range"),
        ],
    )


def part_details(asked: Asked) -> Answer:
    if not asked.question.part:
        return which_part("which_part_stock", "tell me about the alternator")
    parts = pick_parts(asked)
    if parts is None:
        return part_not_found(asked)
    shop_branch = branch_id(asked)
    recent_first = asked.today - timedelta(days=RECENT_DAYS - 1)
    found = asked.db.execute(
        select(Part).where(Part.organization_id == asked.organization_id, parts.condition)
    ).scalars().all()
    rows = []
    for part in found:
        one = Part.id == part.id
        by_branch = _stock_by_branch(asked, one, shop_branch)
        rows.append({
            "name": part.name, "sku": part.sku, "brand": part.brand, "category": part.category,
            "stock_total": sum(row["pieces"] for row in by_branch), "stock_by_branch": by_branch,
            "min_stock": part.min_stock,
            "sold_last_30_days": _sold_since(asked, one, shop_branch, recent_first),
            "expected_next_30_days": _forecast(asked, one, shop_branch),
            "open_alerts": len(_open_alerts(asked, one, shop_branch)),
            **({"sale_price_money": part.sale_price or 0, "unit_cost_money": part.unit_cost or 0} if asked.currency else {}),
        })
    rows.sort(key=lambda row: (-row["sold_last_30_days"], row["sku"]))
    shown = rows[:SHOWN_ROWS]
    totals = {key: sum(row[key] for row in rows) for key in ("stock_total", "sold_last_30_days", "expected_next_30_days")}
    first = shown[0]
    return Answer(
        "part_details",
        {"subject": parts.subject, **asked.place(), "matches": len(rows), "totals": totals, "parts": shown},
        f"{parts.title}{where_words(asked)}: {len(rows)} {'part' if len(rows) == 1 else 'parts'}, "
        f"{pieces(totals['stock_total'])} in stock, {pieces(totals['sold_last_30_days'])} sold in the last {RECENT_DAYS} days, "
        f"about {pieces(totals['expected_next_30_days'])} expected in the next {HORIZON_DAYS} days. "
        f"Best seller: {first['name']} ({first['sku']}).",
        [
            Number(key="matching_parts", label="Matching parts", value=len(rows), unit="count"),
            Number(key="in_stock", label="In stock now", value=totals["stock_total"], unit="pieces"),
            Number(key="sold_last_30_days", label="Sold, last 30 days", value=totals["sold_last_30_days"], unit="pieces"),
            Number(key="expected_next_30_days", label="Expected, next 30 days", value=totals["expected_next_30_days"], unit="pieces"),
        ]
        + [Number(label=f"{row['name']} ({row['sku']})", value=row["stock_total"], unit="pieces") for row in shown],
    )


def _days_counted_over(part_ids: tuple, shop_branch: uuid.UUID | None) -> str:
    """Days out of stock are added up per part and per branch: "parts_and_branches", "branches" or "one"."""
    if part_ids:
        return "parts_and_branches"
    return "one" if shop_branch else "branches"


def _average_price(asked: Asked, condition, shop_branch: uuid.UUID | None, first: date, last: date) -> int | None:
    """Average selling price in centimes over the priced sales of [first, last], None without any."""
    query = (
        select(func.sum(SaleLine.quantity * SaleLine.unit_price), func.sum(SaleLine.quantity))
        .join(Part, Part.id == SaleLine.part_id)
        .where(SaleLine.organization_id == asked.organization_id, SaleLine.sold_on.between(first, last),
               SaleLine.unit_price.is_not(None), condition)
    )
    value, quantity = asked.db.execute(_in_branch(query, SaleLine.branch_id, shop_branch)).one()
    return round(value / quantity) if quantity else None


def _in_branch(query, column, shop_branch: uuid.UUID | None):
    return query.where(column == shop_branch) if shop_branch else query


def _stock(asked: Asked, condition, shop_branch: uuid.UUID | None) -> int:
    query = select(func.coalesce(func.sum(StockLevel.quantity), 0)).join(Part, Part.id == StockLevel.part_id).where(
        StockLevel.organization_id == asked.organization_id, condition
    )
    return int(asked.db.scalar(_in_branch(query, StockLevel.branch_id, shop_branch)))


def _stock_by_branch(asked: Asked, condition, shop_branch: uuid.UUID | None) -> list[dict]:
    query = (
        select(Branch.name, func.sum(StockLevel.quantity))
        .join(Branch, Branch.id == StockLevel.branch_id)
        .join(Part, Part.id == StockLevel.part_id)
        .where(StockLevel.organization_id == asked.organization_id, condition)
        .group_by(Branch.name)
        .order_by(Branch.name)
    )
    return [{"branch": name, "pieces": int(quantity)} for name, quantity in asked.db.execute(_in_branch(query, StockLevel.branch_id, shop_branch))]


def _sold_since(asked: Asked, condition, shop_branch: uuid.UUID | None, first: date) -> int:
    query = select(func.coalesce(func.sum(SaleLine.quantity), 0)).join(Part, Part.id == SaleLine.part_id).where(
        SaleLine.organization_id == asked.organization_id, SaleLine.sold_on.between(first, asked.today), condition
    )
    return int(asked.db.scalar(_in_branch(query, SaleLine.branch_id, shop_branch)))


def _forecast(asked: Asked, condition, shop_branch: uuid.UUID | None) -> int:
    query = select(func.coalesce(func.sum(Forecast.quantity), 0)).join(Part, Part.id == Forecast.part_id).where(
        Forecast.organization_id == asked.organization_id, Forecast.horizon_days == HORIZON_DAYS, condition
    )
    return round(asked.db.scalar(_in_branch(query, Forecast.branch_id, shop_branch)))


def _days_out_of_stock(asked: Asked, condition, shop_branch: uuid.UUID | None, first: date, last: date) -> int:
    """Days with zero stock inside [first, last], one per branch that was out."""
    query = select(StockOut.first_day, StockOut.last_day).join(Part, Part.id == StockOut.part_id).where(
        StockOut.organization_id == asked.organization_id, StockOut.first_day <= last, StockOut.last_day >= first, condition
    )
    rows = asked.db.execute(_in_branch(query, StockOut.branch_id, shop_branch))
    return sum((min(out_last, last) - max(out_first, first)).days + 1 for out_first, out_last in rows)


def _open_alerts(asked: Asked, condition, shop_branch: uuid.UUID | None) -> list[dict]:
    query = (
        select(Alert.kind, Alert.sentence, Branch.name)
        .join(Part, Part.id == Alert.part_id)
        .join(Branch, Branch.id == Alert.branch_id)
        .where(Alert.organization_id == asked.organization_id, Alert.status == "open", condition)
        .order_by(Alert.raised_on.desc())
        .limit(SHOWN_ROWS)
    )
    return [{"kind": kind, "branch": name, "what": sentence} for kind, sentence, name in asked.db.execute(_in_branch(query, Alert.branch_id, shop_branch))]
