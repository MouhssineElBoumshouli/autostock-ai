"""Turning approved suggestions into purchase orders, sending them, and receiving stock.

One open (draft) purchase order per supplier at a time: approving a line adds it to that
supplier's draft order, creating one if there isn't one yet. Rejecting an approved line takes
it back off; an order with no lines left is removed. Once an order is sent its lines are locked:
the suggestion stays "approved" for history, but can no longer be edited or rejected.
"""

import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import record_change
from app.db import utc_now
from app.models import Branch, OrderSuggestion, Part, PurchaseOrder, PurchaseOrderLine, StockLevel, Supplier, User
from app.ordering.delivery_time import days_taken, learn_from_deliveries

Key = tuple[uuid.UUID, uuid.UUID]  # (part_id, branch_id)


def on_order_by_key(db: Session, organization_id: uuid.UUID) -> dict[Key, int]:
    """Pieces already on their way: sent but not yet received, grouped by part and branch."""
    rows = db.execute(
        select(
            PurchaseOrderLine.part_id,
            PurchaseOrderLine.branch_id,
            func.sum(PurchaseOrderLine.quantity - PurchaseOrderLine.received_quantity),
        )
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.purchase_order_id)
        .where(PurchaseOrder.organization_id == organization_id, PurchaseOrder.status == "sent")
        .group_by(PurchaseOrderLine.part_id, PurchaseOrderLine.branch_id)
    )
    return {(part, branch): int(total) for part, branch, total in rows if total > 0}


def decide_suggestion(
    db: Session, user: User, suggestion: OrderSuggestion, decision: str, quantity: int | None
) -> OrderSuggestion:
    """`decision` is "approve" or "reject". `quantity` overrides the suggested amount when approving."""
    line, po = _current_line(db, suggestion)
    if po is not None and po.status != "draft":
        raise HTTPException(409, "This line is already on a purchase order that was sent.")
    part = db.get_one(Part, suggestion.part_id)
    branch = db.get_one(Branch, suggestion.branch_id)

    if decision == "reject":
        if line is not None:
            suggestion.purchase_order_line_id = None
            db.flush()  # clear the reference before the line can be deleted
            _remove_line(db, po, line)
        before = {"status": suggestion.status}
        suggestion.status, suggestion.approved_quantity = "rejected", None
        record_change(db, user, "order_suggestion.rejected", "order_suggestion", suggestion.id, before=before,
                      after={"status": "rejected", "part": part.name, "branch": branch.name})
        return suggestion

    if suggestion.supplier_id is None:
        raise HTTPException(422, "This part has no supplier, so it can't go on a purchase order.")
    qty = quantity if quantity is not None else suggestion.quantity
    if qty <= 0:
        raise HTTPException(422, "Enter a quantity of at least 1.")

    if po is None:
        po = _draft_order_for_supplier(db, user, suggestion.supplier_id)
        line = PurchaseOrderLine(organization_id=suggestion.organization_id, purchase_order_id=po.id,
                                 part_id=suggestion.part_id, branch_id=suggestion.branch_id,
                                 quantity=qty, unit_cost=part.unit_cost)
        db.add(line)
        db.flush()
        suggestion.purchase_order_line_id = line.id
    else:
        line.quantity, line.unit_cost = qty, part.unit_cost

    before = {"status": suggestion.status, "quantity": suggestion.approved_quantity}
    suggestion.status, suggestion.approved_quantity = "approved", qty
    record_change(db, user, "order_suggestion.approved", "order_suggestion", suggestion.id, before=before,
                  after={"status": "approved", "quantity": qty, "order_number": po.order_number,
                        "part": part.name, "branch": branch.name})
    return suggestion


def approve_all_for_supplier(
    db: Session, user: User, suggestions: list[OrderSuggestion]
) -> list[OrderSuggestion]:
    return [decide_suggestion(db, user, suggestion, "approve", None) for suggestion in suggestions]


def send_purchase_order(db: Session, user: User, po: PurchaseOrder) -> PurchaseOrder:
    if po.status != "draft":
        raise HTTPException(409, "Only a draft order can be sent.")
    po.status, po.sent_at = "sent", utc_now()
    supplier = db.get_one(Supplier, po.supplier_id)
    record_change(db, user, "purchase_order.sent", "purchase_order", po.id,
                  after={"order_number": po.order_number, "supplier": supplier.name})
    return po


def receive_purchase_order(
    db: Session, user: User, po: PurchaseOrder, received: dict[uuid.UUID, int]
) -> PurchaseOrder:
    """`received` is how many of each line arrived now (0 is fine: that line just hasn't arrived yet)."""
    if po.status != "sent":
        raise HTTPException(409, "Only a sent order can be received.")
    lines = {line.id: line for line in
             db.scalars(select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == po.id))}
    unknown = set(received) - set(lines)
    if unknown:
        raise HTTPException(404, "One of these lines is not on this order.")

    for line_id, quantity in received.items():
        line = lines[line_id]
        remaining = line.quantity - line.received_quantity
        if not 0 <= quantity <= remaining:
            raise HTTPException(422, f"Enter a quantity from 0 to {remaining} for this line.")
        if quantity == 0:
            continue
        level = _stock_level(db, po.organization_id, line.part_id, line.branch_id)
        before_quantity = level.quantity
        level.quantity += quantity
        line.received_quantity += quantity
        part = db.get_one(Part, line.part_id)
        branch = db.get_one(Branch, line.branch_id)
        record_change(db, user, "stock_level.received", "stock_level", level.id,
                      before={"quantity": before_quantity},
                      after={"quantity": level.quantity, "order_number": po.order_number,
                            "part": part.name, "branch": branch.name})

    db.flush()
    if all(line.received_quantity >= line.quantity for line in lines.values()):
        po.status, po.received_at = "received", utc_now()
        po.days_taken = days_taken(po.sent_at, po.received_at)
        supplier = db.get_one(Supplier, po.supplier_id)
        record_change(db, user, "purchase_order.received", "purchase_order", po.id,
                      after={"order_number": po.order_number, "supplier": supplier.name, "days_taken": po.days_taken})
        db.flush()  # so this delivery counts in what is learned
        learn_from_deliveries(db, user, supplier)
    return po


def _current_line(db: Session, suggestion: OrderSuggestion) -> tuple[PurchaseOrderLine | None, PurchaseOrder | None]:
    if suggestion.purchase_order_line_id is None:
        return None, None
    line = db.get_one(PurchaseOrderLine, suggestion.purchase_order_line_id)
    return line, db.get_one(PurchaseOrder, line.purchase_order_id)


def _remove_line(db: Session, po: PurchaseOrder, line: PurchaseOrderLine) -> None:
    db.delete(line)
    db.flush()
    remaining = db.scalar(
        select(func.count()).select_from(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == po.id)
    )
    if not remaining:
        db.delete(po)


def _draft_order_for_supplier(db: Session, user: User, supplier_id: uuid.UUID) -> PurchaseOrder:
    po = db.scalar(
        select(PurchaseOrder)
        .where(PurchaseOrder.organization_id == user.organization_id, PurchaseOrder.supplier_id == supplier_id,
               PurchaseOrder.status == "draft")
        .with_for_update()
    )
    if po is not None:
        return po
    po = PurchaseOrder(organization_id=user.organization_id, supplier_id=supplier_id, created_by=user.id,
                       order_number=_next_order_number(db, user.organization_id), status="draft")
    db.add(po)
    db.flush()
    supplier = db.get_one(Supplier, supplier_id)
    record_change(db, user, "purchase_order.created", "purchase_order", po.id,
                  after={"order_number": po.order_number, "supplier": supplier.name})
    return po


def _next_order_number(db: Session, organization_id: uuid.UUID) -> str:
    count = db.scalar(
        select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.organization_id == organization_id)
    ) or 0
    return f"PO-{count + 1:04d}"


def _stock_level(db: Session, organization_id: uuid.UUID, part_id: uuid.UUID, branch_id: uuid.UUID) -> StockLevel:
    level = db.scalar(
        select(StockLevel).where(StockLevel.part_id == part_id, StockLevel.branch_id == branch_id).with_for_update()
    )
    if level is None:
        level = StockLevel(organization_id=organization_id, part_id=part_id, branch_id=branch_id, quantity=0)
        db.add(level)
        db.flush()
    return level
