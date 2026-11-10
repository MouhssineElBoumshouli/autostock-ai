"""Purchase orders: one per supplier, built from approved suggestions. A manager marks one sent,
then receives it (even partially) once parts arrive; receiving adds the quantities to stock.

Staff see everything here except money (CLAUDE.md "staff never get money"): each money field has
its own model (`*WithMoney`), built only for owners and managers, the same way app/api/today.py does it."""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import require_role
from app.db import get_session
from app.models import Branch, Part, PurchaseOrder, PurchaseOrderLine, Supplier, User
from app.ordering.purchase_orders import receive_purchase_order, send_purchase_order

router = APIRouter(prefix="/api/orders/purchase-orders")
managers = require_role("owner", "manager")
anyone = require_role()

Status = Literal["draft", "sent", "received"]


class LineOut(BaseModel):
    """What staff see: no money."""

    id: uuid.UUID
    part_id: uuid.UUID
    part_sku: str
    part_name: str
    branch_id: uuid.UUID
    branch_name: str
    quantity: int
    received_quantity: int


class LineOutWithMoney(LineOut):
    """What owners and managers also see."""

    unit_cost: int | None
    line_cost: int


class PurchaseOrderOut(BaseModel):
    """What staff see."""

    id: uuid.UUID
    order_number: str
    status: Status
    created_at: datetime
    sent_at: datetime | None
    received_at: datetime | None
    supplier_id: uuid.UUID
    supplier_name: str
    supplier_phone: str | None
    supplier_email: str | None
    lines: list[LineOutWithMoney | LineOut]


class PurchaseOrderOutWithMoney(PurchaseOrderOut):
    """What owners and managers also see."""

    total_cost: int


class PurchaseOrderSummary(BaseModel):
    """What staff see."""

    id: uuid.UUID
    order_number: str
    status: Status
    created_at: datetime
    sent_at: datetime | None
    received_at: datetime | None
    supplier_id: uuid.UUID
    supplier_name: str
    line_count: int


class PurchaseOrderSummaryWithMoney(PurchaseOrderSummary):
    """What owners and managers also see."""

    total_cost: int


class ReceiveRequest(BaseModel):
    lines: dict[uuid.UUID, int]  # purchase order line id -> quantity received now


@router.get("")
def list_purchase_orders(
    status: Status | None = None, user: User = Depends(anyone), db: Session = Depends(get_session)
) -> list[PurchaseOrderSummaryWithMoney | PurchaseOrderSummary]:
    filters = [PurchaseOrder.organization_id == user.organization_id]
    if status:
        filters.append(PurchaseOrder.status == status)
    orders = db.scalars(select(PurchaseOrder).where(*filters).order_by(PurchaseOrder.created_at.desc())).all()
    suppliers = _supplier_names(db, user.organization_id)
    costs, counts = _cost_and_count_by_order(db, user.organization_id)
    can_see_money = user.role != "staff"
    summaries = []
    for po in orders:
        fields = dict(
            id=po.id, order_number=po.order_number, status=po.status, created_at=po.created_at,
            sent_at=po.sent_at, received_at=po.received_at, supplier_id=po.supplier_id,
            supplier_name=suppliers.get(po.supplier_id, "?"), line_count=counts.get(po.id, 0),
        )
        summaries.append(
            PurchaseOrderSummaryWithMoney(**fields, total_cost=costs.get(po.id, 0)) if can_see_money
            else PurchaseOrderSummary(**fields)
        )
    return summaries


@router.get("/{po_id}")
def get_purchase_order(
    po_id: uuid.UUID, user: User = Depends(anyone), db: Session = Depends(get_session)
) -> PurchaseOrderOutWithMoney | PurchaseOrderOut:
    return _out(db, _find(db, user, po_id), can_see_money=user.role != "staff")


@router.post("/{po_id}/send")
def send(po_id: uuid.UUID, user: User = Depends(managers), db: Session = Depends(get_session)) -> PurchaseOrderOutWithMoney:
    po = _find(db, user, po_id, lock=True)
    send_purchase_order(db, user, po)
    db.commit()
    return _out(db, po, can_see_money=True)


@router.post("/{po_id}/receive")
def receive(
    po_id: uuid.UUID, body: ReceiveRequest, user: User = Depends(managers), db: Session = Depends(get_session)
) -> PurchaseOrderOutWithMoney:
    po = _find(db, user, po_id, lock=True)
    receive_purchase_order(db, user, po, body.lines)
    db.commit()
    return _out(db, po, can_see_money=True)


def _find(db: Session, user: User, po_id: uuid.UUID, lock: bool = False) -> PurchaseOrder:
    query = select(PurchaseOrder).where(PurchaseOrder.id == po_id, PurchaseOrder.organization_id == user.organization_id)
    po = db.scalar(query.with_for_update() if lock else query)
    if po is None:
        raise HTTPException(404, "This purchase order is not in your shop.")
    return po


def _out(db: Session, po: PurchaseOrder, can_see_money: bool) -> PurchaseOrderOutWithMoney | PurchaseOrderOut:
    supplier = db.get_one(Supplier, po.supplier_id)
    rows = db.execute(
        select(PurchaseOrderLine, Part.sku, Part.name, Branch.name)
        .join(Part, Part.id == PurchaseOrderLine.part_id)
        .join(Branch, Branch.id == PurchaseOrderLine.branch_id)
        .where(PurchaseOrderLine.purchase_order_id == po.id)
        .order_by(Part.name)
    ).all()
    lines: list[LineOutWithMoney | LineOut] = []
    total_cost = 0
    for line, sku, name, branch_name in rows:
        line_cost = line.quantity * (line.unit_cost or 0)
        total_cost += line_cost
        fields = dict(id=line.id, part_id=line.part_id, part_sku=sku, part_name=name, branch_id=line.branch_id,
                      branch_name=branch_name, quantity=line.quantity, received_quantity=line.received_quantity)
        lines.append(LineOutWithMoney(**fields, unit_cost=line.unit_cost, line_cost=line_cost) if can_see_money else LineOut(**fields))
    order_fields = dict(
        id=po.id, order_number=po.order_number, status=po.status, created_at=po.created_at, sent_at=po.sent_at,
        received_at=po.received_at, supplier_id=po.supplier_id, supplier_name=supplier.name,
        supplier_phone=supplier.phone, supplier_email=supplier.email, lines=lines,
    )
    if can_see_money:
        return PurchaseOrderOutWithMoney(**order_fields, total_cost=total_cost)
    return PurchaseOrderOut(**order_fields)


def _supplier_names(db: Session, organization_id: uuid.UUID) -> dict[uuid.UUID, str]:
    rows = db.execute(select(Supplier.id, Supplier.name).where(Supplier.organization_id == organization_id))
    return dict(rows.all())


def _cost_and_count_by_order(db: Session, organization_id: uuid.UUID) -> tuple[dict[uuid.UUID, int], dict[uuid.UUID, int]]:
    rows = db.execute(
        select(PurchaseOrderLine.purchase_order_id, PurchaseOrderLine.quantity, PurchaseOrderLine.unit_cost)
        .where(PurchaseOrderLine.organization_id == organization_id)
    )
    costs: dict[uuid.UUID, int] = {}
    counts: dict[uuid.UUID, int] = {}
    for po_id, quantity, unit_cost in rows:
        costs[po_id] = costs.get(po_id, 0) + quantity * (unit_cost or 0)
        counts[po_id] = counts.get(po_id, 0) + 1
    return costs, counts
