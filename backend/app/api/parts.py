"""One part: everything about it (side panel), and editing it (owners and managers)."""

import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import NameText
from app.audit import record_change
from app.auth.permissions import require_role
from app.db import get_session
from app.equivalents import reachable_from
from app.models import Branch, Part, PartEquivalent, SaleLine, StockLevel, Supplier, User
from app.stock_status import StockStatus, status_for

router = APIRouter(prefix="/api/parts")
anyone = require_role()
can_edit = require_role("owner", "manager")

SALES_SHOWN = 10
OptionalText = Annotated[str | None, Field(max_length=300)]
Count = Annotated[int, Field(ge=0, le=10_000_000)]
Money = Annotated[int, Field(ge=0, le=10_000_000_000)]


class SupplierOut(BaseModel):
    id: uuid.UUID
    name: str
    phone: str | None
    email: str | None
    delivery_days: int | None


class BranchStock(BaseModel):
    branch_id: uuid.UUID
    branch: str
    quantity: int


class SaleOut(BaseModel):
    sold_on: date
    branch: str
    quantity: int
    unit_price: int | None


class EquivalentPart(BaseModel):
    link_id: uuid.UUID | None  # None for a same-OEM-number match: automatic, so there is nothing to remove
    part_id: uuid.UUID
    sku: str
    name: str
    brand: str | None
    price: int | None
    quantity: int
    stock: list[BranchStock]
    in_stock: bool
    reason_type: Literal["oem", "manual", "supplier_file"]
    linked_by: str | None  # the manager who made a "manual" link


class PartDetail(BaseModel):
    id: uuid.UUID
    sku: str
    name: str
    brand: str | None
    category: str | None
    oem_reference: str | None
    unit_cost: int | None
    sale_price: int | None
    min_stock: int
    is_active: bool
    quantity: int
    status: StockStatus
    supplier: SupplierOut | None
    stock: list[BranchStock]
    last_sales: list[SaleOut]
    equivalents: list[EquivalentPart]


class EquivalentChange(BaseModel):
    other_part_id: uuid.UUID


class StockChange(BaseModel):
    branch_id: uuid.UUID
    quantity: Count


class PartChange(BaseModel):
    name: NameText | None = None
    brand: OptionalText = None
    category: OptionalText = None
    oem_reference: OptionalText = None
    unit_cost: Money | None = None
    sale_price: Money | None = None
    min_stock: Count | None = None
    supplier_id: uuid.UUID | None = None
    is_active: bool | None = None
    stock: list[StockChange] | None = None


# Fields that may be emptied by sending null.
CLEARABLE = {"brand", "category", "oem_reference", "unit_cost", "sale_price", "supplier_id"}


@router.get("/{part_id}")
def read_part(part_id: uuid.UUID, user: User = Depends(anyone), db: Session = Depends(get_session)) -> PartDetail:
    return describe(db, find_part(db, user, part_id))


@router.patch("/{part_id}")
def change_part(
    part_id: uuid.UUID,
    body: PartChange,
    user: User = Depends(can_edit),
    db: Session = Depends(get_session),
) -> PartDetail:
    part = find_part(db, user, part_id, lock=True)
    before = snapshot(db, part)

    for key in body.model_fields_set - {"stock"}:
        value = getattr(body, key)
        if value is None and key not in CLEARABLE:
            continue
        if isinstance(value, str):
            value = " ".join(value.split()) or None
        if key == "supplier_id" and value is not None:
            find_in_shop(db, Supplier, value, user, "This supplier is not in your shop.")
        setattr(part, key, value)

    for change in body.stock or []:
        find_in_shop(db, Branch, change.branch_id, user, "This branch is not in your shop.")
        level = db.scalar(
            select(StockLevel).where(StockLevel.part_id == part.id, StockLevel.branch_id == change.branch_id)
        )
        if level is None:
            db.add(StockLevel(organization_id=user.organization_id, part_id=part.id, branch_id=change.branch_id, quantity=change.quantity))
        else:
            level.quantity = change.quantity
    db.flush()

    after = snapshot(db, part)
    if after != before:
        record_change(db, user, "part.updated", "part", part.id, before=before, after=after)
    db.commit()
    return describe(db, part)


@router.post("/{part_id}/equivalents")
def link_equivalent(
    part_id: uuid.UUID,
    body: EquivalentChange,
    user: User = Depends(can_edit),
    db: Session = Depends(get_session),
) -> PartDetail:
    part = find_part(db, user, part_id)
    if body.other_part_id == part_id:
        raise HTTPException(422, "A part can't be its own equivalent.")
    other = find_part(db, user, body.other_part_id)

    part_a_id, part_b_id = sorted([part.id, other.id])
    exists = db.scalar(
        select(PartEquivalent.id).where(
            PartEquivalent.organization_id == user.organization_id,
            PartEquivalent.part_a_id == part_a_id,
            PartEquivalent.part_b_id == part_b_id,
        )
    )
    if exists:
        raise HTTPException(422, "These parts are already linked.")

    link = PartEquivalent(
        organization_id=user.organization_id,
        part_a_id=part_a_id,
        part_b_id=part_b_id,
        source="manual",
        created_by_user_id=user.id,
    )
    db.add(link)
    db.flush()
    record_change(
        db, user, "part_equivalent.linked", "part_equivalent", link.id,
        after={"part": _part_label(part), "other_part": _part_label(other), "source": "manual"},
    )
    db.commit()
    return describe(db, part)


@router.delete("/{part_id}/equivalents/{link_id}")
def unlink_equivalent(
    part_id: uuid.UUID,
    link_id: uuid.UUID,
    user: User = Depends(can_edit),
    db: Session = Depends(get_session),
) -> PartDetail:
    part = find_part(db, user, part_id)
    link = db.scalar(
        select(PartEquivalent).where(
            PartEquivalent.id == link_id,
            PartEquivalent.organization_id == user.organization_id,
            (PartEquivalent.part_a_id == part_id) | (PartEquivalent.part_b_id == part_id),
        )
    )
    if link is None:
        raise HTTPException(404, "This link is not in your shop.")
    other_id = link.part_b_id if link.part_a_id == part_id else link.part_a_id
    other = db.get(Part, other_id)

    record_change(
        db, user, "part_equivalent.removed", "part_equivalent", link.id,
        before={"part": _part_label(part), "other_part": _part_label(other), "source": link.source},
    )
    db.delete(link)
    db.commit()
    return describe(db, part)


def _part_label(part: Part) -> str:
    return f"{part.name} ({part.sku})"


def find_part(db: Session, user: User, part_id: uuid.UUID, lock: bool = False) -> Part:
    query = select(Part).where(Part.id == part_id, Part.organization_id == user.organization_id)
    part = db.scalar(query.with_for_update() if lock else query)
    if part is None:
        raise HTTPException(404, "This part is not in your shop.")
    return part


def find_in_shop(db: Session, model, row_id: uuid.UUID, user: User, message: str) -> None:
    if db.scalar(select(model.id).where(model.id == row_id, model.organization_id == user.organization_id)) is None:
        raise HTTPException(422, message)


def stock_by_branch(db: Session, part: Part) -> list[BranchStock]:
    """Every branch of the shop, with 0 where the part has no stock."""
    rows = db.execute(
        select(Branch.id, Branch.name, StockLevel.quantity)
        .outerjoin(StockLevel, (StockLevel.branch_id == Branch.id) & (StockLevel.part_id == part.id))
        .where(Branch.organization_id == part.organization_id)
        .order_by(Branch.created_at)
    ).all()
    return [BranchStock(branch_id=row.id, branch=row.name, quantity=row.quantity or 0) for row in rows]


def snapshot(db: Session, part: Part) -> dict:
    """What the audit log stores about a part."""
    supplier = db.get(Supplier, part.supplier_id) if part.supplier_id else None
    return {
        "sku": part.sku,
        "name": part.name,
        "brand": part.brand,
        "category": part.category,
        "oem_reference": part.oem_reference,
        "unit_cost": part.unit_cost,
        "sale_price": part.sale_price,
        "min_stock": part.min_stock,
        "supplier": supplier.name if supplier else None,
        "is_active": part.is_active,
        "stock": {row.branch: row.quantity for row in stock_by_branch(db, part)},
    }


def describe(db: Session, part: Part) -> PartDetail:
    stock = stock_by_branch(db, part)
    quantity = sum(row.quantity for row in stock)
    supplier = db.get(Supplier, part.supplier_id) if part.supplier_id else None
    sales = db.execute(
        select(SaleLine.sold_on, Branch.name, SaleLine.quantity, SaleLine.unit_price)
        .join(Branch, Branch.id == SaleLine.branch_id)
        .where(SaleLine.part_id == part.id, SaleLine.organization_id == part.organization_id)
        .order_by(SaleLine.sold_on.desc(), SaleLine.created_at.desc())
        .limit(SALES_SHOWN)
    ).all()
    return PartDetail(
        id=part.id,
        sku=part.sku,
        name=part.name,
        brand=part.brand,
        category=part.category,
        oem_reference=part.oem_reference,
        unit_cost=part.unit_cost,
        sale_price=part.sale_price,
        min_stock=part.min_stock,
        is_active=part.is_active,
        quantity=quantity,
        status=status_for(part.is_active, quantity, part.min_stock),
        supplier=SupplierOut.model_validate(supplier, from_attributes=True) if supplier else None,
        stock=stock,
        last_sales=[SaleOut(sold_on=s.sold_on, branch=s.name, quantity=s.quantity, unit_price=s.unit_price) for s in sales],
        equivalents=equivalents_of(db, part),
    )


def equivalents_of(db: Session, part: Part) -> list[EquivalentPart]:
    """Every part from another brand considered the same part, in stock first."""
    reached = reachable_from(db, part.organization_id, part.id)
    if not reached:
        return []

    others = {
        other.id: other
        for other in db.scalars(select(Part).where(Part.id.in_([r.part_id for r in reached])))
    }
    managers = dict(
        db.execute(select(User.id, User.name).where(User.id.in_([r.linked_by for r in reached if r.linked_by]))).all()
    )

    equivalents = []
    for r in reached:
        other = others.get(r.part_id)
        if other is None:
            continue
        stock = stock_by_branch(db, other)
        quantity = sum(row.quantity for row in stock)
        equivalents.append(
            EquivalentPart(
                link_id=r.link_id,
                part_id=other.id,
                sku=other.sku,
                name=other.name,
                brand=other.brand,
                price=other.sale_price,
                quantity=quantity,
                stock=stock,
                in_stock=quantity > 0,
                reason_type=r.reason_type,
                linked_by=managers.get(r.linked_by) if r.linked_by else None,
            )
        )
    return sorted(equivalents, key=lambda e: (not e.in_stock, e.name))
