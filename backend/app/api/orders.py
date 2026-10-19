"""What to order: a manager asks for suggestions (optionally within a budget), approves, edits
or rejects each line, and reads them back. Approving turns a line into a purchase order line
(see app/api/purchase_orders.py)."""

import uuid
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
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


class SuggestionsRequest(BaseModel):
    budget: int | None = Field(default=None, ge=0)  # centimes; None = no limit


class LineOut(BaseModel):
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
    days_covered: int
    expected: float
    cushion: float
    need: int
    unit_cost: int | None
    line_cost: int
    missed_sales_prevented: float
    value_per_dirham: float | None
    reason: str


class RunOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    history_last_day: date | None
    budget: int | None
    suggested_cost: int
    kept_cost: int
    kept_lines: int
    cut_lines: int
    lines: list[LineOut]


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
def new_suggestions(body: SuggestionsRequest, user: User = Depends(managers), db: Session = Depends(get_session)) -> RunOut:
    run = make_order_run(db, user, body.budget)
    db.commit()
    return _run_out(db, run)


@router.get("/suggestions/latest")
def latest_suggestions(user: User = Depends(anyone), db: Session = Depends(get_session)) -> RunOut | None:
    run = db.scalar(
        select(OrderRun).where(OrderRun.organization_id == user.organization_id).order_by(OrderRun.created_at.desc()).limit(1)
    )
    return _run_out(db, run) if run else None


@router.post("/suggestions/{suggestion_id}/decide")
def decide(
    suggestion_id: uuid.UUID, body: DecisionRequest, user: User = Depends(managers), db: Session = Depends(get_session)
) -> LineOut:
    suggestion = _find_suggestion(db, user, suggestion_id)
    decide_suggestion(db, user, suggestion, body.decision, body.quantity)
    db.commit()
    return _line_out(db, suggestion)


@router.post("/runs/{run_id}/suppliers/{supplier_id}/approve-all")
def approve_all(
    run_id: uuid.UUID, supplier_id: uuid.UUID, user: User = Depends(managers), db: Session = Depends(get_session)
) -> list[LineOut]:
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
    return [_line_out(db, suggestion) for suggestion in suggestions]


def _find_suggestion(db: Session, user: User, suggestion_id: uuid.UUID) -> OrderSuggestion:
    suggestion = db.scalar(
        select(OrderSuggestion).where(
            OrderSuggestion.id == suggestion_id, OrderSuggestion.organization_id == user.organization_id
        ).with_for_update()
    )
    if suggestion is None:
        raise HTTPException(404, "This suggestion is not in your shop.")
    return suggestion


def _run_out(db: Session, run: OrderRun) -> RunOut:
    lines = db.scalars(
        select(OrderSuggestion)
        .where(OrderSuggestion.organization_id == run.organization_id, OrderSuggestion.run_id == run.id)
        .order_by(OrderSuggestion.status.desc(), OrderSuggestion.value_per_dirham.desc().nulls_first())
    ).all()
    names = _names(db, run.organization_id)
    return RunOut(
        **{field: getattr(run, field) for field in RunOut.model_fields if field != "lines"},
        lines=[_line_out(db, line, names) for line in lines],
    )


def _line_out(db: Session, line: OrderSuggestion, names: dict[uuid.UUID, tuple[str, str]] | None = None) -> LineOut:
    names = names or _names(db, line.organization_id)
    part_sku, part_name = names[line.part_id]
    branch_name = names[line.branch_id][0]
    supplier_name = names.get(line.supplier_id, (None,))[0] if line.supplier_id else None
    return LineOut(
        id=line.id, part_id=line.part_id, part_sku=part_sku, part_name=part_name, branch_id=line.branch_id,
        branch_name=branch_name, supplier_id=line.supplier_id, supplier_name=supplier_name, status=line.status,
        rule=line.rule, quantity=line.quantity, approved_quantity=line.approved_quantity, on_hand=line.on_hand,
        on_order=line.on_order, pack_size=line.pack_size, delivery_days=line.delivery_days,
        days_covered=line.days_covered, expected=line.expected, cushion=line.cushion, need=line.need,
        unit_cost=line.unit_cost, line_cost=line.line_cost, missed_sales_prevented=line.missed_sales_prevented,
        value_per_dirham=line.value_per_dirham, reason=line.reason,
    )


def _names(db: Session, organization_id: uuid.UUID) -> dict[uuid.UUID, tuple[str, str]]:
    """id -> (primary text, secondary text). Parts: (sku, name). Branches and suppliers: (name, name)."""
    found: dict[uuid.UUID, tuple[str, str]] = {}
    for part_id, sku, name in db.execute(select(Part.id, Part.sku, Part.name).where(Part.organization_id == organization_id)):
        found[part_id] = (sku, name)
    for branch_id, name in db.execute(select(Branch.id, Branch.name).where(Branch.organization_id == organization_id)):
        found[branch_id] = (name, name)
    for supplier_id, name in db.execute(select(Supplier.id, Supplier.name).where(Supplier.organization_id == organization_id)):
        found[supplier_id] = (name, name)
    return found
