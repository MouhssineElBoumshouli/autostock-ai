"""Suppliers: the owner can add one, rename, set its contact details, merge (moving its parts to
another supplier) or remove one that no part uses. Delivery times fill in by themselves (see
app/ordering/delivery_time.py); the owner may still type one, or empty it to go back to automatic.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.schemas import NameText
from app.audit import record_change
from app.auth.permissions import require_role
from app.db import get_session
from app.models import OrderSuggestion, Part, Supplier, User
from app.ordering.delivery_time import DeliveryTime, RecentDeliveries, deliveries_disagree, delivery_time, set_by_owner

router = APIRouter(prefix="/api/suppliers")
owner_only = require_role("owner")


class SupplierOut(BaseModel):
    id: uuid.UUID
    name: str
    phone: str | None = None
    email: str | None = None
    delivery_days: int | None = None  # what the owner sees in the edit field (None: automatic, not known yet)
    delivery: DeliveryTime  # what "what to order" uses, and where it came from
    # A typed delivery time that 3+ real deliveries disagree with: what they say (Settings offers it).
    deliveries_say: RecentDeliveries | None = None
    in_use: bool  # has parts pointing to it; can be merged but not removed


class SupplierCreate(BaseModel):
    name: NameText
    phone: str | None = None
    email: str | None = None
    delivery_days: int | None = None


class SupplierRename(BaseModel):
    name: NameText


class SupplierDetails(BaseModel):
    phone: str | None = None
    email: str | None = None
    delivery_days: int | None = None


class SupplierMerge(BaseModel):
    into: uuid.UUID


def _out(db: Session, supplier: Supplier, used: set[uuid.UUID]) -> SupplierOut:
    return SupplierOut(
        id=supplier.id, name=supplier.name, phone=supplier.phone, email=supplier.email,
        delivery_days=supplier.delivery_days, delivery=delivery_time(supplier),
        deliveries_say=deliveries_disagree(db, supplier), in_use=supplier.id in used,
    )


def _snapshot(supplier: Supplier) -> dict:
    return {"phone": supplier.phone, "email": supplier.email}


@router.get("")
def list_suppliers(owner: User = Depends(owner_only), db: Session = Depends(get_session)) -> list[SupplierOut]:
    suppliers = db.scalars(
        select(Supplier).where(Supplier.organization_id == owner.organization_id).order_by(Supplier.name)
    ).all()
    used = _suppliers_in_use(db, owner.organization_id)
    return [_out(db, supplier, used) for supplier in suppliers]


@router.post("", status_code=201)
def add_supplier(
    body: SupplierCreate,
    owner: User = Depends(owner_only),
    db: Session = Depends(get_session),
) -> SupplierOut:
    _check_name_free(db, owner, body.name, exclude=None)
    supplier = Supplier(organization_id=owner.organization_id, name=body.name, phone=body.phone, email=body.email)
    db.add(supplier)
    db.flush()
    record_change(
        db, owner, "supplier.added", "supplier", supplier.id,
        after={"name": supplier.name, **_snapshot(supplier)},
    )
    set_by_owner(db, owner, supplier, body.delivery_days)
    db.commit()
    return _out(db, supplier, set())


@router.patch("/{supplier_id}")
def rename_supplier(
    supplier_id: uuid.UUID,
    body: SupplierRename,
    owner: User = Depends(owner_only),
    db: Session = Depends(get_session),
) -> SupplierOut:
    supplier = _find(db, owner, supplier_id, lock=True)
    _check_name_free(db, owner, body.name, exclude=supplier.id)
    before = supplier.name
    supplier.name = body.name
    if supplier.name != before:
        record_change(
            db, owner, "supplier.renamed", "supplier", supplier.id, before={"name": before}, after={"name": supplier.name}
        )
    db.commit()
    return _out(db, supplier, _suppliers_in_use(db, owner.organization_id))


@router.patch("/{supplier_id}/details")
def update_supplier_details(
    supplier_id: uuid.UUID,
    body: SupplierDetails,
    owner: User = Depends(owner_only),
    db: Session = Depends(get_session),
) -> SupplierOut:
    supplier = _find(db, owner, supplier_id, lock=True)
    before = _snapshot(supplier)
    supplier.phone = body.phone
    supplier.email = body.email
    after = _snapshot(supplier)
    if after != before:
        record_change(
            db, owner, "supplier.details_updated", "supplier", supplier.id,
            before={"name": supplier.name, **before}, after={"name": supplier.name, **after},
        )
    set_by_owner(db, owner, supplier, body.delivery_days)
    db.commit()
    return _out(db, supplier, _suppliers_in_use(db, owner.organization_id))


@router.post("/{supplier_id}/merge", status_code=204)
def merge_supplier(
    supplier_id: uuid.UUID,
    body: SupplierMerge,
    owner: User = Depends(owner_only),
    db: Session = Depends(get_session),
) -> None:
    """Points every part that used this supplier to another one, then removes it."""
    source = _find(db, owner, supplier_id, lock=True)
    target = _find(db, owner, body.into, lock=True)
    if source.id == target.id:
        raise HTTPException(422, "Choose a different supplier to merge into.")

    db.execute(update(Part).where(Part.supplier_id == source.id).values(supplier_id=target.id))
    db.execute(update(OrderSuggestion).where(OrderSuggestion.supplier_id == source.id).values(supplier_id=target.id))
    names = {"from": source.name, "into": target.name}
    db.delete(source)
    record_change(db, owner, "supplier.merged", "supplier", target.id, after=names)
    db.commit()


@router.delete("/{supplier_id}", status_code=204)
def remove_supplier(
    supplier_id: uuid.UUID, owner: User = Depends(owner_only), db: Session = Depends(get_session)
) -> None:
    supplier = _find(db, owner, supplier_id, lock=True)
    if supplier.id in _suppliers_in_use(db, owner.organization_id):
        raise HTTPException(409, "This supplier is used by some parts. Merge it into another supplier first.")

    record_change(db, owner, "supplier.removed", "supplier", supplier.id, before={"name": supplier.name})
    # Past suggestions keep their numbers; they just no longer name this supplier.
    db.execute(update(OrderSuggestion).where(OrderSuggestion.supplier_id == supplier.id).values(supplier_id=None))
    db.delete(supplier)
    db.commit()


def _find(db: Session, owner: User, supplier_id: uuid.UUID, lock: bool = False) -> Supplier:
    query = select(Supplier).where(Supplier.id == supplier_id, Supplier.organization_id == owner.organization_id)
    supplier = db.scalar(query.with_for_update() if lock else query)
    if supplier is None:
        raise HTTPException(404, "This supplier is not in your shop.")
    return supplier


def _check_name_free(db: Session, owner: User, name: str, exclude: uuid.UUID | None) -> None:
    filters = [Supplier.organization_id == owner.organization_id, func.lower(Supplier.name) == name.lower()]
    if exclude is not None:
        filters.append(Supplier.id != exclude)
    clash = db.scalar(select(Supplier.id).where(*filters))
    if clash:
        raise HTTPException(409, "A supplier with this name already exists.")


def _suppliers_in_use(db: Session, organization_id: uuid.UUID) -> set[uuid.UUID]:
    rows = db.scalars(
        select(Part.supplier_id).distinct().where(Part.organization_id == organization_id, Part.supplier_id.is_not(None))
    ).all()
    return set(rows)
