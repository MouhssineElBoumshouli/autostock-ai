"""Works out what to order for every part in every branch of one shop, and stores it as one run."""

import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import record_change
from app.models import Forecast, Organization, OrderRun, OrderSuggestion, Part, SaleLine, StockLevel, Supplier, User
from app.ordering.budget import BudgetLine, apply_budget, line_value, missed_sales_prevented, value_per_dirham
from app.ordering.purchase_orders import on_order_by_key
from app.ordering.reasons import reason
from app.ordering.suggest import RECENT_DAYS, SLOW_LOOKBACK_DAYS, HorizonForecast, Position, spread, suggest

DEFAULT_DELIVERY_DAYS = 7  # when the supplier's delivery time is not filled in

Key = tuple[uuid.UUID, uuid.UUID]  # (part_id, branch_id)


def make_order_run(db: Session, user: User, budget: int | None) -> OrderRun:
    """Stores a new run with its lines. The caller commits. Nothing is ordered."""
    organization_id = user.organization_id
    forecasts, last_day = _forecasts(db, organization_id)
    run = OrderRun(organization_id=organization_id, created_by=user.id, history_last_day=last_day, budget=budget,
                   suggested_cost=0, kept_cost=0, kept_lines=0, cut_lines=0)
    db.add(run)
    db.flush()
    if last_day is None:
        record_change(db, user, "order_suggestions.created", "order_run", run.id, after={"lines": 0})
        return run

    stock = _stock(db, organization_id)
    on_order = on_order_by_key(db, organization_id)
    sold_28 = _sold_since(db, organization_id, last_day - timedelta(days=RECENT_DAYS - 1))
    sold_90 = _sold_since(db, organization_id, last_day - timedelta(days=SLOW_LOOKBACK_DAYS - 1))
    parts = {part.id: (part, delivery) for part, delivery in db.execute(
        select(Part, Supplier.delivery_days).outerjoin(Supplier, Supplier.id == Part.supplier_id)
        .where(Part.organization_id == organization_id, Part.is_active)
    )}
    target = db.get_one(Organization, organization_id).order_service_target

    lines, budget_lines = [], []
    for key in sorted(set(forecasts) | set(sold_90)):
        if key[0] not in parts:
            continue
        part, delivery = parts[key[0]]
        line = _line(run, key, part, delivery, forecasts.get(key, ()), stock.get(key, 0), on_order.get(key, 0),
                    sold_28.get(key, 0), sold_90.get(key, 0), target)
        if line is not None:
            lines.append(line)
            value = line_value(line.missed_sales_prevented, part.unit_cost, part.sale_price)
            budget_lines.append(BudgetLine(line, line.line_cost, value))

    kept, cut = apply_budget(budget_lines, budget)
    for item in budget_lines:
        item.key.value_per_dirham = None if item.cost <= 0 else round(value_per_dirham(item), 4)
    for item in cut:
        item.key.status = "cut_by_budget"
        item.key.reason += " Cut to stay within the budget."
    db.add_all(lines)
    run.suggested_cost = sum(line.line_cost for line in lines)
    run.kept_cost = sum(item.cost for item in kept)
    run.kept_lines, run.cut_lines = len(kept), len(cut)
    record_change(db, user, "order_suggestions.created", "order_run", run.id,
                  after={"lines": len(kept), "cut": len(cut), "cost": run.kept_cost, "budget": budget})
    return run


def _line(run: OrderRun, key: Key, part: Part, delivery: int | None, forecasts: tuple, on_hand: int, on_order: int,
          sold_28: int, sold_90: int, target: float) -> OrderSuggestion | None:
    """None when there is nothing to order."""
    delivery_days = delivery if delivery is not None else DEFAULT_DELIVERY_DAYS
    position = Position(on_hand, on_order, part.pack_size, delivery_days, sold_28, sold_90, forecasts)
    s = suggest(position, target)
    if s.quantity <= 0:
        return None
    prevented = missed_sales_prevented(s.expected, spread(forecasts, s.days_covered), on_hand + on_order, s.quantity)
    text = reason(s, delivery_days, on_hand, on_order, part.pack_size, sold_90)
    if delivery is None:
        text += f" (Supplier delivery time not set: {DEFAULT_DELIVERY_DAYS} days assumed.)"
    return OrderSuggestion(
        organization_id=run.organization_id, run_id=run.id, part_id=key[0], branch_id=key[1], supplier_id=part.supplier_id,
        status="suggested", rule=s.rule, quantity=s.quantity, on_hand=on_hand, on_order=on_order, pack_size=part.pack_size,
        delivery_days=delivery_days, days_covered=s.days_covered, expected=round(s.expected, 2), cushion=round(s.cushion, 2),
        need=s.need, sold_last_90_days=sold_90, unit_cost=part.unit_cost, line_cost=s.quantity * (part.unit_cost or 0),
        missed_sales_prevented=round(prevented, 3), value_per_dirham=None, reason=text,
    )


def _forecasts(db: Session, organization_id: uuid.UUID) -> tuple[dict[Key, tuple[HorizonForecast, ...]], date | None]:
    found: dict[Key, list[HorizonForecast]] = defaultdict(list)
    last_day = None
    for row in db.scalars(select(Forecast).where(Forecast.organization_id == organization_id)):
        found[(row.part_id, row.branch_id)].append(HorizonForecast(row.horizon_days, row.quantity, row.high))
        last_day = row.history_last_day
    return {key: tuple(value) for key, value in found.items()}, last_day


def _stock(db: Session, organization_id: uuid.UUID) -> dict[Key, int]:
    rows = db.execute(select(StockLevel.part_id, StockLevel.branch_id, StockLevel.quantity)
                      .where(StockLevel.organization_id == organization_id))
    return {(part, branch): max(quantity, 0) for part, branch, quantity in rows}


def _sold_since(db: Session, organization_id: uuid.UUID, first_day: date) -> dict[Key, int]:
    rows = db.execute(
        select(SaleLine.part_id, SaleLine.branch_id, func.sum(SaleLine.quantity))
        .where(SaleLine.organization_id == organization_id, SaleLine.sold_on >= first_day)
        .group_by(SaleLine.part_id, SaleLine.branch_id)
    )
    return {(part, branch): int(total) for part, branch, total in rows if total > 0}
