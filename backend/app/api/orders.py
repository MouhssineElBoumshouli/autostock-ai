"""What to order: a manager asks for suggestions (optionally within a budget), approves, edits
or rejects each line, and reads them back. Approving turns a line into a purchase order line
(see app/api/purchase_orders.py).

A run is read in two steps, so a big shop never sends all its lines at once: the run with one
total per supplier, then one supplier's lines, 50 at a time.

Staff see everything here except money (CLAUDE.md "staff never get money"): each money field has
its own model (`*WithMoney`), built only for owners and managers, the same way app/api/today.py does it."""

import uuid
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import String, case, cast, func, select
from sqlalchemy.orm import Session

from app.audit import record_change
from app.auth.permissions import require_role
from app.db import get_session
from app.models import Branch, Organization, OrderRun, OrderSuggestion, Part, Supplier, User
from app.ordering.purchase_orders import approve_all_for_supplier, decide_suggestion
from app.ordering.run import make_order_run

router = APIRouter(prefix="/api/orders")
managers = require_role("owner", "manager")
owner_only = require_role("owner")
anyone = require_role()

# Save money (fewer safety stock), Balanced, Never run out (more safety stock).
ServiceTarget = Literal[0.8, 0.9, 0.95]
PAGE_SIZE = 50
DIDNT_FIT = "didnt_fit"  # the group of lines cut by the budget, across suppliers
NO_SUPPLIER = "none"  # the group of lines whose part has no supplier
URGENT_FIRST = (OrderSuggestion.status.desc(), OrderSuggestion.value_per_dirham.desc().nulls_first())


class SuggestionsRequest(BaseModel):
    budget: int | None = Field(default=None, ge=0)  # centimes; None = no limit


class LineOut(BaseModel):
    """What staff see: no money."""

    id: uuid.UUID
    part_id: uuid.UUID
    part_sku: str
    part_name: str
    branch_id: uuid.UUID
    branch_name: str
    supplier_id: uuid.UUID | None
    supplier_name: str | None
    status: str
    rule: str
    quantity: int
    approved_quantity: int | None
    on_hand: int
    on_order: int
    pack_size: int
    delivery_days: int
    delivery_source: str | None  # estimated, file, learned, owner; None on lines made before this was kept
    delivery_learned_from: int
    days_covered: int
    expected: float
    cushion: float
    need: int
    sold_last_90_days: int
    missed_sales_prevented: float
    reason: str  # English; the website builds it in the person's language from the numbers above


class LineOutWithMoney(LineOut):
    """What owners and managers also see."""

    unit_cost: int | None
    line_cost: int
    value_per_dirham: float | None


class GroupOut(BaseModel):
    """One supplier's lines (or the lines with no supplier, or the lines cut by the budget). What staff see."""

    key: str  # the supplier's id, NO_SUPPLIER or DIDNT_FIT
    supplier_id: uuid.UUID | None
    supplier_name: str | None
    line_count: int
    pending_count: int  # lines still waiting for a decision


class GroupOutWithMoney(GroupOut):
    total_cost: int  # what the lines cost, at the approved quantity when there is one


class RunOut(BaseModel):
    """What staff see."""

    id: uuid.UUID
    created_at: datetime
    history_last_day: date | None
    kept_lines: int
    cut_lines: int
    groups: list[GroupOutWithMoney | GroupOut]  # most urgent first, the lines cut by the budget last


class RunOutWithMoney(RunOut):
    """What owners and managers also see."""

    budget: int | None
    suggested_cost: int
    kept_cost: int


class LinesPage(BaseModel):
    items: list[LineOutWithMoney | LineOut]
    total: int
    page: int
    page_size: int


class DecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    quantity: int | None = Field(default=None, ge=1)


class OrderSettingsOut(BaseModel):
    service_target: ServiceTarget


class OrderSettingsChange(BaseModel):
    service_target: ServiceTarget


@router.get("/settings")
def read_order_settings(owner: User = Depends(owner_only), db: Session = Depends(get_session)) -> OrderSettingsOut:
    organization = db.get_one(Organization, owner.organization_id)
    return OrderSettingsOut(service_target=organization.order_service_target)


@router.patch("/settings")
def change_order_settings(
    body: OrderSettingsChange, owner: User = Depends(owner_only), db: Session = Depends(get_session)
) -> OrderSettingsOut:
    organization = db.get_one(Organization, owner.organization_id, with_for_update=True)
    before = organization.order_service_target
    organization.order_service_target = body.service_target
    if organization.order_service_target != before:
        record_change(db, owner, "organization.updated", "organization", organization.id,
                      before={"order_service_target": before}, after={"order_service_target": body.service_target})
    db.commit()
    return OrderSettingsOut(service_target=organization.order_service_target)


@router.post("/suggestions", status_code=201)
def new_suggestions(body: SuggestionsRequest, user: User = Depends(managers), db: Session = Depends(get_session)) -> RunOutWithMoney:
    run = make_order_run(db, user.organization_id, body.budget, user)
    db.commit()
    return _run_out(db, run, can_see_money=True)


@router.get("/suggestions/latest")
def latest_suggestions(user: User = Depends(anyone), db: Session = Depends(get_session)) -> RunOutWithMoney | RunOut | None:
    run = db.scalar(
        select(OrderRun).where(OrderRun.organization_id == user.organization_id).order_by(OrderRun.created_at.desc()).limit(1)
    )
    return _run_out(db, run, can_see_money=user.role != "staff") if run else None


@router.get("/runs/{run_id}/lines")
def run_lines(
    run_id: uuid.UUID, group: str, page: int = Query(1, ge=1), user: User = Depends(anyone), db: Session = Depends(get_session)
) -> LinesPage:
    """One group's lines (see GroupOut.key), most urgent first."""
    in_group = (OrderSuggestion.organization_id == user.organization_id, OrderSuggestion.run_id == run_id, _group_key() == group)
    total = db.scalar(select(func.count()).select_from(OrderSuggestion).where(*in_group))
    lines = db.scalars(
        select(OrderSuggestion).where(*in_group).order_by(*URGENT_FIRST, OrderSuggestion.id)
        .offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    ).all()
    names = _names(db, user.organization_id, lines)
    can_see_money = user.role != "staff"
    return LinesPage(
        items=[_line_out(db, line, names, can_see_money) for line in lines], total=total, page=page, page_size=PAGE_SIZE
    )


@router.post("/suggestions/{suggestion_id}/decide")
def decide(
    suggestion_id: uuid.UUID, body: DecisionRequest, user: User = Depends(managers), db: Session = Depends(get_session)
) -> LineOutWithMoney:
    suggestion = _find_suggestion(db, user, suggestion_id)
    decide_suggestion(db, user, suggestion, body.decision, body.quantity)
    db.commit()
    return _line_out(db, suggestion, can_see_money=True)


@router.post("/runs/{run_id}/suppliers/{supplier_id}/approve-all")
def approve_all(
    run_id: uuid.UUID, supplier_id: uuid.UUID, user: User = Depends(managers), db: Session = Depends(get_session)
) -> dict[str, int]:
    suggestions = db.scalars(
        select(OrderSuggestion).where(
            OrderSuggestion.organization_id == user.organization_id,
            OrderSuggestion.run_id == run_id,
            OrderSuggestion.supplier_id == supplier_id,
            OrderSuggestion.status.in_(("suggested", "cut_by_budget")),
        )
    ).all()
    if not suggestions:
        raise HTTPException(404, "Nothing to approve for this supplier.")
    approve_all_for_supplier(db, user, suggestions)
    db.commit()
    return {"approved": len(suggestions)}


def _find_suggestion(db: Session, user: User, suggestion_id: uuid.UUID) -> OrderSuggestion:
    suggestion = db.scalar(
        select(OrderSuggestion).where(
            OrderSuggestion.id == suggestion_id, OrderSuggestion.organization_id == user.organization_id
        ).with_for_update()
    )
    if suggestion is None:
        raise HTTPException(404, "This suggestion is not in your shop.")
    return suggestion


def _group_key():
    return case(
        (OrderSuggestion.status == "cut_by_budget", DIDNT_FIT),
        (OrderSuggestion.supplier_id.is_(None), NO_SUPPLIER),
        else_=cast(OrderSuggestion.supplier_id, String),
    )


def _run_out(db: Session, run: OrderRun, can_see_money: bool) -> RunOutWithMoney | RunOut:
    """The run with one total per group. Groups come in the order of their most urgent line."""
    ranked = select(
        _group_key().label("key"),
        OrderSuggestion.status,
        (func.coalesce(OrderSuggestion.approved_quantity, OrderSuggestion.quantity)
         * func.coalesce(OrderSuggestion.unit_cost, 0)).label("cost"),
        func.row_number().over(order_by=URGENT_FIRST).label("rank"),
    ).where(OrderSuggestion.organization_id == run.organization_id, OrderSuggestion.run_id == run.id).subquery()
    rows = db.execute(
        select(
            ranked.c.key,
            func.min(ranked.c.rank),
            func.count(),
            func.count().filter(ranked.c.status.in_(("suggested", "cut_by_budget"))),
            func.sum(ranked.c.cost),
        ).group_by(ranked.c.key)
    ).all()
    suppliers = dict(db.execute(select(Supplier.id, Supplier.name).where(Supplier.organization_id == run.organization_id)).all())
    groups: list[GroupOutWithMoney | GroupOut] = []
    for key, _rank, count, pending, cost in sorted(rows, key=lambda row: (row[0] == DIDNT_FIT, row[1])):
        supplier_id = None if key in (DIDNT_FIT, NO_SUPPLIER) else uuid.UUID(key)
        fields = dict(key=key, supplier_id=supplier_id, supplier_name=suppliers.get(supplier_id), line_count=count, pending_count=pending)
        groups.append(GroupOutWithMoney(**fields, total_cost=cost) if can_see_money else GroupOut(**fields))
    run_fields = dict(id=run.id, created_at=run.created_at, history_last_day=run.history_last_day,
                      kept_lines=run.kept_lines, cut_lines=run.cut_lines, groups=groups)
    if can_see_money:
        return RunOutWithMoney(**run_fields, budget=run.budget, suggested_cost=run.suggested_cost, kept_cost=run.kept_cost)
    return RunOut(**run_fields)


def _line_out(
    db: Session, line: OrderSuggestion, names: dict[uuid.UUID, tuple[str, str]] | None = None, can_see_money: bool = True
) -> LineOutWithMoney | LineOut:
    names = names or _names(db, line.organization_id, [line])
    part_sku, part_name = names[line.part_id]
    branch_name = names[line.branch_id][0]
    supplier_name = names.get(line.supplier_id, (None,))[0] if line.supplier_id else None
    fields = dict(
        id=line.id, part_id=line.part_id, part_sku=part_sku, part_name=part_name, branch_id=line.branch_id,
        branch_name=branch_name, supplier_id=line.supplier_id, supplier_name=supplier_name, status=line.status,
        rule=line.rule, quantity=line.quantity, approved_quantity=line.approved_quantity, on_hand=line.on_hand,
        on_order=line.on_order, pack_size=line.pack_size, delivery_days=line.delivery_days,
        delivery_source=line.delivery_source, delivery_learned_from=line.delivery_learned_from,
        days_covered=line.days_covered, expected=line.expected, cushion=line.cushion, need=line.need,
        sold_last_90_days=line.sold_last_90_days, missed_sales_prevented=line.missed_sales_prevented, reason=line.reason,
    )
    if can_see_money:
        return LineOutWithMoney(**fields, unit_cost=line.unit_cost, line_cost=line.line_cost, value_per_dirham=line.value_per_dirham)
    return LineOut(**fields)


def _names(db: Session, organization_id: uuid.UUID, lines: list[OrderSuggestion]) -> dict[uuid.UUID, tuple[str, str]]:
    """id -> (primary text, secondary text). Parts (only those of `lines`): (sku, name).
    Branches and suppliers: (name, name)."""
    found: dict[uuid.UUID, tuple[str, str]] = {}
    part_ids = {line.part_id for line in lines}
    for part_id, sku, name in db.execute(
        select(Part.id, Part.sku, Part.name).where(Part.organization_id == organization_id, Part.id.in_(part_ids))
    ):
        found[part_id] = (sku, name)
    for branch_id, name in db.execute(select(Branch.id, Branch.name).where(Branch.organization_id == organization_id)):
        found[branch_id] = (name, name)
    for supplier_id, name in db.execute(select(Supplier.id, Supplier.name).where(Supplier.organization_id == organization_id)):
        found[supplier_id] = (name, name)
    return found
