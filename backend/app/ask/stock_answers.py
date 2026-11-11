"""Answers about stock: how many on the shelf, what runs out soon, dead stock, and forecasts."""

import uuid

from sqlalchemy import func, select

from app.alerts.problem import day_label, pieces
from app.ask.answer_parts import (
    SHOWN_PARTS, SHOWN_ROWS, Answer, Asked, Number, PartPick, branch_id, part_not_found, pick_parts, where_words,
    which_part,
)
from app.models import Branch, Forecast, Part, StockLevel
from app.runs_out import HORIZON_DAYS, RUNNING_OUT_WITHIN_DAYS, expected_30d_subquery, shown_runs_out_days
from app.stock_status import DEAD_AFTER_DAYS, is_dead, quantity_on_hand


def stock_of_part(asked: Asked) -> Answer:
    if not asked.question.part:
        return which_part("which_part_stock", "how many oil filters in stock")
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
    numbers = [Number(label=name, value=quantity, unit="pieces") for name, quantity in per_branch]
    if parts.part_ids:
        numbers += _per_part_stock(asked, parts, shop_branch)
    return Answer(
        "stock_of_part", {"subject": parts.subject, **asked.place(), "pieces": total},
        f"{parts.title}: {pieces(total)} in stock{where_words(asked)}.", numbers,
    )


def _per_part_stock(asked: Asked, parts: PartPick, shop_branch: uuid.UUID | None) -> list[Number]:
    """One line per matched part (top SHOWN_PARTS, most in stock first), scoped to the branch
    asked about if any, else summed over every branch."""
    on_hand = quantity_on_hand(asked.organization_id, shop_branch)
    rows = asked.db.execute(
        select(Part.name, Part.sku, on_hand.c.quantity)
        .join(on_hand, on_hand.c.part_id == Part.id)
        .where(Part.organization_id == asked.organization_id, parts.condition)
        .order_by(on_hand.c.quantity.desc(), Part.sku)
        .limit(SHOWN_PARTS)
    ).all()
    return [Number(label=f"{name} ({sku})", value=int(quantity), unit="pieces") for name, sku, quantity in rows]


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
    values = {"subject": parts.subject, **asked.place(), "days": RUNNING_OUT_WITHIN_DAYS}
    if not rows:
        return Answer("running_out_none", values, f"Nothing in {parts.label} is expected to run out{when}.")
    return Answer(
        "running_out",
        {**values, "count": len(rows), "name": rows[0].name, "sku": rows[0].sku, "pieces": int(rows[0].quantity),
         "days_left": shown_runs_out_days(rows[0][3])},
        f"{len(rows)} {'part is' if len(rows) == 1 else 'parts are'} expected to run out{when} ({parts.label}). "
        f"First: {rows[0].name} ({rows[0].sku}), {pieces(int(rows[0].quantity))} left, about "
        f"{shown_runs_out_days(rows[0][3])} days.",
        [Number(key="parts_running_out", label="Parts running out", value=len(rows), unit="count")]
        + [Number(key="days_left", about=f"{name} ({sku})", label=f"{name} ({sku}), days left",
                  value=shown_runs_out_days(left), unit="days")
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
    values = {"subject": parts.subject, **asked.place(), "days": DEAD_AFTER_DAYS}
    if not rows:
        return Answer("dead_stock_none", values, f"No dead stock in {parts.label}{where_words(asked)} ({when}).")
    total_pieces = sum(int(row.quantity) for row in rows)
    total_value = sum(int(row[3]) for row in rows)
    return Answer(
        "dead_stock",
        {**values, "count": len(rows), "pieces": total_pieces, **asked.money_value(total_value)},
        f"{len(rows)} {'part has' if len(rows) == 1 else 'parts have'} stock but {when} ({parts.label}"
        f"{where_words(asked)}): {pieces(total_pieces)} on the shelf{asked.money_words(total_value, ', costing ')}.",
        [
            Number(key="dead_parts", label="Dead stock parts", value=len(rows), unit="count"),
            Number(key="pieces_on_shelf", label="Pieces on the shelf", value=total_pieces, unit="pieces"),
            *asked.money_number("value_at_cost", "Value at cost", total_value),
        ]
        + [Number(label=f"{name} ({sku})", value=int(quantity), unit="pieces") for name, sku, quantity, _ in rows[:SHOWN_ROWS]],
    )


def forecast_of_part(asked: Asked) -> Answer:
    if not asked.question.part:
        return which_part("which_part_forecast", "how many brake pads will we sell")
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
        return Answer(
            "forecast_none", {"subject": parts.subject},
            f"No forecast yet for {parts.label}. Forecasts are made after sales are imported.",
        )
    numbers = [
        Number(key="expected_next_30_days", label=f"Expected, next {HORIZON_DAYS} days", value=round(expected), unit="pieces"),
        Number(key="likely_at_least", label="Likely at least", value=round(low), unit="pieces"),
        Number(key="likely_at_most", label="Likely at most", value=round(high), unit="pieces"),
        Number(key="made_from_sales_up_to", label="Made from sales up to", value=made_from.isoformat(), unit="date"),
    ]
    if parts.part_ids:
        numbers += _per_part_forecast(asked, parts, shop_branch)
    return Answer(
        "forecast",
        {"subject": parts.subject, **asked.place(), "pieces": round(expected), "low": round(low), "high": round(high),
         "days": HORIZON_DAYS, "made_from": made_from.isoformat()},
        f"{parts.title}{where_words(asked)}: about {pieces(round(expected))} expected over the next "
        f"{HORIZON_DAYS} days (likely between {round(low)} and {round(high)}), from sales up to {day_label(made_from)}.",
        numbers,
    )


def _per_part_forecast(asked: Asked, parts: PartPick, shop_branch: uuid.UUID | None) -> list[Number]:
    """One line per matched part (top SHOWN_PARTS, most expected first)."""
    expected = func.sum(Forecast.quantity)
    query = (
        select(Part.name, Part.sku, expected)
        .join(Part, Part.id == Forecast.part_id)
        .where(Forecast.organization_id == asked.organization_id, Forecast.horizon_days == HORIZON_DAYS, parts.condition)
        .group_by(Part.id, Part.name, Part.sku)
        .order_by(expected.desc(), Part.sku)
        .limit(SHOWN_PARTS)
    )
    if shop_branch:
        query = query.where(Forecast.branch_id == shop_branch)
    rows = asked.db.execute(query).all()
    return [Number(label=f"{name} ({sku})", value=round(quantity), unit="pieces") for name, sku, quantity in rows]
