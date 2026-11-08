"""Works out what to order for every part in every branch of one shop, and stores it as one run."""

import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import record_change
from app.models import (
    Forecast, Organization, OrderRun, OrderSuggestion, Part, PurchaseOrder, PurchaseOrderLine, SaleLine, StockLevel,
    Supplier, User,
)
from app.ordering.budget import BudgetLine, apply_budget, line_value, missed_sales_prevented, value_per_dirham
from app.ordering.delivery_time import DeliveryTime, delivery_time
from app.ordering.purchase_orders import on_order_by_key
from app.ordering.reasons import reason
from app.ordering.suggest import RECENT_DAYS, SLOW_LOOKBACK_DAYS, HorizonForecast, Position, spread, suggest

Key = tuple[uuid.UUID, uuid.UUID]  # (part_id, branch_id)


def last_budget(db: Session, organization_id: uuid.UUID) -> int | None:
    """The budget the owner last set (None included: that can mean "no limit"), for the automatic
    run that follows a forecast run, so it doesn't quietly drop back to unlimited."""
    run = db.scalar(
        select(OrderRun).where(OrderRun.organization_id == organization_id).order_by(OrderRun.created_at.desc()).limit(1)
    )
    return run.budget if run else None


def make_order_run(db: Session, organization_id: uuid.UUID, budget: int | None, user: User | None = None) -> OrderRun:
    """Stores a new run with its lines. The caller commits. Nothing is ordered.
    A line a person already decided on carries over unchanged: a line approved (and possibly
    edited) while its purchase order is still a draft stays approved, with the same quantity and
    the same purchase order line -- the fresh math has no other way to know a draft order already
    covers it, so without this it would be suggested again. Once that order is sent, the usual math
    already counts it as on order, so the part is free to be computed fresh again (and suggested
    further if the need has grown since). A rejected line stays rejected unless the part has since
    run out. This way an automatic run (after every forecast run) never undoes what a manager
    already decided. `user` is None for the run made automatically after a forecast run: not a
    person's action, so nothing goes in the audit log for it (like the alerts engine's own
    automatic runs)."""
    forecasts, last_day = _forecasts(db, organization_id)
    # Read before the new run is added: once flushed, it would itself be "the latest run".
    previous = _previous_decisions(db, organization_id)
    run = OrderRun(organization_id=organization_id, created_by=user.id if user else None, history_last_day=last_day,
                   budget=budget, suggested_cost=0, kept_cost=0, kept_lines=0, cut_lines=0)
    db.add(run)
    db.flush()
    if last_day is None:
        if user is not None:
            record_change(db, user, "order_suggestions.created", "order_run", run.id, after={"lines": 0})
        return run

    stock = _stock(db, organization_id)
    on_order = on_order_by_key(db, organization_id)
    sold_28 = _sold_since(db, organization_id, last_day - timedelta(days=RECENT_DAYS - 1))
    sold_90 = _sold_since(db, organization_id, last_day - timedelta(days=SLOW_LOOKBACK_DAYS - 1))
    parts = {part.id: (part, delivery_time(supplier)) for part, supplier in db.execute(
        select(Part, Supplier).outerjoin(Supplier, Supplier.id == Part.supplier_id)
        .where(Part.organization_id == organization_id, Part.is_active)
    )}
    target = db.get_one(Organization, organization_id).order_service_target

    approved, rejected, budget_lines = [], [], []
    for key in sorted(set(forecasts) | set(sold_90) | set(previous)):
        prior = previous.get(key)
        if prior is not None and prior.status == "approved":
            approved.append(_carry_over(run, prior))
            continue
        if key[0] not in parts:
            continue
        part, delivery = parts[key[0]]
        line = _line(run, key, part, delivery, forecasts.get(key, ()), stock.get(key, 0), on_order.get(key, 0),
                    sold_28.get(key, 0), sold_90.get(key, 0), target)
        if line is None:
            continue
        if prior is not None and prior.status == "rejected" and not _need_clearly_grew(prior, line):
            line.status = "rejected"
            rejected.append(line)
            continue
        value = line_value(line.missed_sales_prevented, part.unit_cost, part.sale_price)
        budget_lines.append(BudgetLine(line, line.line_cost, value))

    approved_cost = sum(item.line_cost for item in approved)
    kept, cut = apply_budget(budget_lines, None if budget is None else max(budget - approved_cost, 0))
    for item in budget_lines:
        item.key.value_per_dirham = None if item.cost <= 0 else round(value_per_dirham(item), 4)
    for item in cut:
        item.key.status = "cut_by_budget"
        item.key.reason += " Cut to stay within the budget."
    fresh = [item.key for item in budget_lines]
    db.add_all(approved + rejected + fresh)
    run.suggested_cost = approved_cost + sum(item.cost for item in budget_lines)
    run.kept_cost = approved_cost + sum(item.cost for item in kept)
    run.kept_lines = len(approved) + len(kept)
    run.cut_lines = len(cut)
    if user is not None:
        record_change(db, user, "order_suggestions.created", "order_run", run.id,
                      after={"lines": run.kept_lines, "cut": run.cut_lines, "cost": run.kept_cost, "budget": budget})
    return run


def _line(run: OrderRun, key: Key, part: Part, delivery: DeliveryTime, forecasts: tuple, on_hand: int, on_order: int,
          sold_28: int, sold_90: int, target: float) -> OrderSuggestion | None:
    """None when there is nothing to order."""
    position = Position(on_hand, on_order, part.pack_size, delivery.days, sold_28, sold_90, forecasts)
    s = suggest(position, target)
    if s.quantity <= 0:
        return None
    prevented = missed_sales_prevented(s.expected, spread(forecasts, s.days_covered), on_hand + on_order, s.quantity)
    text = reason(s, delivery, on_hand, on_order, part.pack_size, sold_90)
    return OrderSuggestion(
        organization_id=run.organization_id, run_id=run.id, part_id=key[0], branch_id=key[1], supplier_id=part.supplier_id,
        status="suggested", rule=s.rule, quantity=s.quantity, on_hand=on_hand, on_order=on_order, pack_size=part.pack_size,
        delivery_days=delivery.days, delivery_source=delivery.source, delivery_learned_from=delivery.learned_from,
        days_covered=s.days_covered, expected=round(s.expected, 2), cushion=round(s.cushion, 2),
        need=s.need, sold_last_90_days=sold_90, unit_cost=part.unit_cost, line_cost=s.quantity * (part.unit_cost or 0),
        missed_sales_prevented=round(prevented, 3), value_per_dirham=None, reason=text,
    )


def _carry_over(run: OrderRun, prior: OrderSuggestion) -> OrderSuggestion:
    """A new row for the new run, an exact copy of an approved line: same quantity, same purchase
    order line, so it is never suggested twice or silently cut by a tighter budget."""
    return OrderSuggestion(
        organization_id=run.organization_id, run_id=run.id, part_id=prior.part_id, branch_id=prior.branch_id,
        supplier_id=prior.supplier_id, status=prior.status, rule=prior.rule, quantity=prior.quantity,
        on_hand=prior.on_hand, on_order=prior.on_order, pack_size=prior.pack_size, delivery_days=prior.delivery_days,
        delivery_source=prior.delivery_source, delivery_learned_from=prior.delivery_learned_from,
        days_covered=prior.days_covered, expected=prior.expected, cushion=prior.cushion, need=prior.need,
        sold_last_90_days=prior.sold_last_90_days, unit_cost=prior.unit_cost, line_cost=prior.line_cost,
        missed_sales_prevented=prior.missed_sales_prevented, value_per_dirham=prior.value_per_dirham,
        reason=prior.reason, approved_quantity=prior.approved_quantity,
        purchase_order_line_id=prior.purchase_order_line_id,
    )


def _need_clearly_grew(prior: OrderSuggestion, fresh: OrderSuggestion) -> bool:
    """Whether a rejected line should be suggested again: the part had stock when it was rejected
    and has since run out."""
    return prior.on_hand > 0 and fresh.on_hand <= 0


def _previous_decisions(db: Session, organization_id: uuid.UUID) -> dict[Key, OrderSuggestion]:
    """The latest run's rejected lines, and its approved lines still on a draft order (one still
    sent or received is left for the usual math, which already knows about it), by part and
    branch."""
    latest_run_id = db.scalar(
        select(OrderRun.id).where(OrderRun.organization_id == organization_id).order_by(OrderRun.created_at.desc()).limit(1)
    )
    if latest_run_id is None:
        return {}
    rows = db.execute(
        select(OrderSuggestion, PurchaseOrder.status)
        .outerjoin(PurchaseOrderLine, PurchaseOrderLine.id == OrderSuggestion.purchase_order_line_id)
        .outerjoin(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.purchase_order_id)
        .where(OrderSuggestion.run_id == latest_run_id, OrderSuggestion.status.in_(("approved", "rejected")))
    )
    return {
        (suggestion.part_id, suggestion.branch_id): suggestion
        for suggestion, po_status in rows
        if suggestion.status == "rejected" or po_status == "draft"
    }


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
