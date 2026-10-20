"""Answers about stock: how many on the shelf, what runs out soon, dead stock, and forecasts."""

from sqlalchemy import func, select

from app.alerts.problem import day_label, pieces
from app.ask.answer_parts import (
    SHOWN_ROWS, Answer, Asked, Number, branch_id, part_not_found, pick_parts, where_words, which_part,
)
from app.models import Branch, Forecast, Part, StockLevel
from app.runs_out import HORIZON_DAYS, RUNNING_OUT_WITHIN_DAYS, expected_30d_subquery, shown_runs_out_days
from app.stock_status import DEAD_AFTER_DAYS, is_dead, quantity_on_hand


def stock_of_part(asked: Asked) -> Answer:
    if not asked.question.part:
        return which_part("how many oil filters in stock")
    parts = pick_parts(asked)
    if parts is None:
        return part_not_found(asked)
    query = (
        select(Branch.name, func.coalesce(func.sum(StockLevel.quantity), 0))
        .join(StockLevel, (StockLevel.branch_id == Branch.id) & (StockLevel.organization_id == asked.organization_id))
        .join(Part, Part.id == StockLevel.part_id)
        .where(Branch.organization_id == asked.organization_id, parts.condition)
        .group_by(Branch.name)
        .order_by(Branch.name)
    )
    shop_branch = branch_id(asked)
    if shop_branch:
        query = query.where(Branch.id == shop_branch)
    per_branch = [(name, int(quantity)) for name, quantity in asked.db.execute(query)]
    total = sum(quantity for _, quantity in per_branch)
    return Answer(
        f"{parts.label.capitalize()}: {pieces(total)} in stock{where_words(asked)}.",
        [Number(label=name, value=quantity, unit="pieces") for name, quantity in per_branch],
    )


def running_out(asked: Asked) -> Answer:
    parts = pick_parts(asked)
    shop_branch = branch_id(asked)
    on_hand = quantity_on_hand(asked.organization_id, shop_branch)
    expected = expected_30d_subquery(asked.organization_id, shop_branch)
    days = on_hand.c.quantity * HORIZON_DAYS / expected.c.expected_30d
    rows = asked.db.execute(
        select(Part.name, Part.sku, on_hand.c.quantity, days)
        .join(on_hand, on_hand.c.part_id == Part.id)
        .join(expected, expected.c.part_id == Part.id)
        .where(
            Part.organization_id == asked.organization_id, Part.is_active, parts.condition,
            on_hand.c.quantity > 0, expected.c.expected_30d > 0, days <= RUNNING_OUT_WITHIN_DAYS,
        )
        .order_by(days, Part.sku)
    ).all()
    when = f"{where_words(asked)} within {RUNNING_OUT_WITHIN_DAYS} days"
    if not rows:
        return Answer(f"Nothing in {parts.label} is expected to run out{when}.")
    return Answer(
        f"{len(rows)} {'part is' if len(rows) == 1 else 'parts are'} expected to run out{when} ({parts.label}). "
        f"First: {rows[0].name} ({rows[0].sku}), {pieces(int(rows[0].quantity))} left, about "
        f"{shown_runs_out_days(rows[0][3])} days.",
        [Number(label="Parts running out", value=len(rows), unit="count")]
        + [Number(label=f"{name} ({sku}), days left", value=shown_runs_out_days(left), unit="days")
           for name, sku, _, left in rows[:SHOWN_ROWS]],
    )


def dead_stock(asked: Asked) -> Answer:
    parts = pick_parts(asked)
    shop_branch = branch_id(asked)
    on_hand = quantity_on_hand(asked.organization_id, shop_branch)
    value = on_hand.c.quantity * func.coalesce(Part.unit_cost, 0)
    rows = asked.db.execute(
        select(Part.name, Part.sku, on_hand.c.quantity, value)
        .join(on_hand, on_hand.c.part_id == Part.id)
        .where(Part.organization_id == asked.organization_id, parts.condition,
               is_dead(on_hand.c.quantity, shop_branch, asked.today))
        .order_by((value if asked.currency else on_hand.c.quantity).desc(), Part.sku)
    ).all()
    when = f"no sale in {DEAD_AFTER_DAYS} days"
    if not rows:
        return Answer(f"No dead stock in {parts.label}{where_words(asked)} ({when}).")
    total_pieces = sum(int(row.quantity) for row in rows)
    total_value = sum(int(row[3]) for row in rows)
    return Answer(
        f"{len(rows)} {'part has' if len(rows) == 1 else 'parts have'} stock but {when} ({parts.label}"
        f"{where_words(asked)}): {pieces(total_pieces)} on the shelf{asked.money_words(total_value, ', costing ')}.",
        [
            Number(label="Dead stock parts", value=len(rows), unit="count"),
            Number(label="Pieces on the shelf", value=total_pieces, unit="pieces"),
            *asked.money_number("Value at cost", total_value),
        ]
        + [Number(label=f"{name} ({sku})", value=int(quantity), unit="pieces") for name, sku, quantity, _ in rows[:SHOWN_ROWS]],
    )


def forecast_of_part(asked: Asked) -> Answer:
    if not asked.question.part:
        return which_part("how many brake pads will we sell")
    parts = pick_parts(asked)
    if parts is None:
        return part_not_found(asked)
    query = (
        select(func.sum(Forecast.quantity), func.sum(Forecast.low), func.sum(Forecast.high), func.max(Forecast.history_last_day))
        .join(Part, Part.id == Forecast.part_id)
        .where(Forecast.organization_id == asked.organization_id, Forecast.horizon_days == HORIZON_DAYS, parts.condition)
    )
    shop_branch = branch_id(asked)
    if shop_branch:
        query = query.where(Forecast.branch_id == shop_branch)
    expected, low, high, made_from = asked.db.execute(query).one()
    if expected is None:
        return Answer(f"No forecast yet for {parts.label}. Forecasts are made after sales are imported.")
    return Answer(
        f"{parts.label.capitalize()}{where_words(asked)}: about {pieces(round(expected))} expected over the next "
        f"{HORIZON_DAYS} days (likely between {round(low)} and {round(high)}), from sales up to {day_label(made_from)}.",
        [
            Number(label=f"Expected, next {HORIZON_DAYS} days", value=round(expected), unit="pieces"),
            Number(label="Likely at least", value=round(low), unit="pieces"),
            Number(label="Likely at most", value=round(high), unit="pieces"),
            Number(label="Made from sales up to", value=made_from.isoformat(), unit="date"),
        ],
    )
