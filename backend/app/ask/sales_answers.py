"""Answers about sales: how much sold, best sellers, and this period against the one before."""

import uuid
from datetime import date

from sqlalchemy import func, select

from app.alerts.problem import pieces
from app.ask.answer_parts import (
    SHOWN_PARTS, SHOWN_ROWS, Answer, Asked, Number, PartPick, branch_id, part_not_found, pick_parts, range_words,
    where_words,
)
from app.ask.periods import LABELS, day_range, period_used, range_before
from app.models import Part, SaleLine


def sales_of(asked: Asked) -> Answer:
    parts = pick_parts(asked)
    if parts is None:
        return part_not_found(asked)
    period = period_used(asked.question.type, asked.question.period)
    first, last = day_range(period, asked.today)
    shop_branch = branch_id(asked)
    sold, value = _sold(asked, parts, shop_branch, first, last)
    numbers = [
        Number(label="Pieces sold", value=sold, unit="pieces"),
        *asked.money_number("Sales value", value),
        Number(label="From", value=first.isoformat(), unit="date"),
        Number(label="To", value=last.isoformat(), unit="date"),
    ]
    if parts.part_ids:
        numbers += _per_part_sales(asked, parts, shop_branch, first, last)
    return Answer(
        f"{parts.title}: {pieces(sold)} sold{where_words(asked)} {LABELS[period]} "
        f"({range_words(first, last)}){asked.money_words(value)}.",
        numbers,
    )


def _per_part_sales(asked: Asked, parts: PartPick, shop_branch: uuid.UUID | None, first: date, last: date) -> list[Number]:
    """One line per matched part (top SHOWN_PARTS, most sold first)."""
    quantity = func.coalesce(func.sum(SaleLine.quantity), 0)
    rows = asked.db.execute(
        _sales_query(asked, parts, shop_branch, first, last, Part.name, Part.sku, quantity)
        .group_by(Part.id, Part.name, Part.sku)
        .order_by(quantity.desc(), Part.sku)
        .limit(SHOWN_PARTS)
    ).all()
    return [Number(label=f"{name} ({sku})", value=int(sold), unit="pieces") for name, sku, sold in rows]


def best_sellers(asked: Asked) -> Answer:
    parts = pick_parts(asked)
    period = period_used(asked.question.type, asked.question.period)
    first, last = day_range(period, asked.today)
    quantity = func.sum(SaleLine.quantity)
    rows = asked.db.execute(
        _sales_query(asked, parts, branch_id(asked), first, last, Part.name, Part.sku, quantity)
        .group_by(Part.id, Part.name, Part.sku)
        .order_by(quantity.desc(), Part.sku)
        .limit(SHOWN_ROWS)
    ).all()
    when = f"{where_words(asked)} {LABELS[period]} ({range_words(first, last)})"
    if not rows:
        return Answer(f"No sales for {parts.label}{when}.")
    name, sku, sold = rows[0]
    return Answer(
        f"Best seller for {parts.label}{when}: {name} ({sku}), {pieces(int(sold))}.",
        [Number(label=f"{name} ({sku})", value=int(sold), unit="pieces") for name, sku, sold in rows],
    )


def sales_vs_last(asked: Asked) -> Answer:
    parts = pick_parts(asked)
    if parts is None:
        return part_not_found(asked)
    period = period_used(asked.question.type, asked.question.period)
    first, last = day_range(period, asked.today)
    before_first, before_last = range_before(period, asked.today)
    shop_branch = branch_id(asked)
    now, now_value = _sold(asked, parts, shop_branch, first, last)
    before, before_value = _sold(asked, parts, shop_branch, before_first, before_last)
    if before == 0:
        change = "with no sales in the period before"
    else:
        percent = round(100 * (now - before) / before)
        change = "the same as" if percent == 0 else f"{'up' if percent > 0 else 'down'} {abs(percent)}% on"
        change += f" {range_words(before_first, before_last)} ({pieces(before)})"
    return Answer(
        f"{parts.title}{where_words(asked)}, {LABELS[period]} ({range_words(first, last)}): "
        f"{pieces(now)}, {change}.",
        [
            Number(label="Pieces sold, this period", value=now, unit="pieces"),
            Number(label="Pieces sold, period before", value=before, unit="pieces"),
            *asked.money_number("Sales value, this period", now_value),
            *asked.money_number("Sales value, period before", before_value),
            Number(label="This period", value=f"{first.isoformat()} to {last.isoformat()}", unit="text"),
            Number(label="Period before", value=f"{before_first.isoformat()} to {before_last.isoformat()}", unit="text"),
        ],
    )


def _sales_query(asked: Asked, parts: PartPick, shop_branch: uuid.UUID | None, first: date, last: date, *columns):
    query = (
        select(*columns)
        .join(Part, Part.id == SaleLine.part_id)
        .where(SaleLine.organization_id == asked.organization_id, SaleLine.sold_on.between(first, last), parts.condition)
    )
    return query.where(SaleLine.branch_id == shop_branch) if shop_branch else query


def _sold(asked: Asked, parts: PartPick, shop_branch: uuid.UUID | None, first: date, last: date) -> tuple[int, int]:
    """Pieces sold and their sales value in centimes (lines without a price count as 0)."""
    quantity, value = asked.db.execute(
        _sales_query(
            asked, parts, shop_branch, first, last,
            func.coalesce(func.sum(SaleLine.quantity), 0),
            func.coalesce(func.sum(SaleLine.quantity * SaleLine.unit_price), 0),
        )
    ).one()
    return int(quantity), int(value)
