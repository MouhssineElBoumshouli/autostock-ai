"""The Stock screen: stat cards, filter choices, and the parts list (50 per page)."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.auth.permissions import require_role
from app.db import get_session
from app.models import Branch, Part, Supplier, User
from app.stock_status import StockStatus, is_dead, quantity_on_hand, status_of

router = APIRouter(prefix="/api/stock")
anyone = require_role()

PAGE_SIZE = 50
StatusFilter = Literal["healthy", "low", "out", "inactive", "dead"]
SortKey = Literal["name", "sku", "brand", "quantity", "min_stock", "status", "supplier"]
STATUS_ORDER = {"out": 0, "low": 1, "healthy": 2, "inactive": 3}


class StockSummary(BaseModel):
    all: int
    healthy: int
    low: int
    out: int


class Choice(BaseModel):
    id: uuid.UUID
    name: str


class StockFilters(BaseModel):
    categories: list[str]
    branches: list[Choice]
    suppliers: list[Choice]


class PartRow(BaseModel):
    id: uuid.UUID
    sku: str
    name: str
    brand: str | None
    category: str | None
    quantity: int
    min_stock: int
    status: StockStatus
    supplier: str | None


class PartsPage(BaseModel):
    items: list[PartRow]
    total: int
    page: int
    page_size: int


@router.get("/summary")
def stock_summary(user: User = Depends(anyone), db: Session = Depends(get_session)) -> StockSummary:
    """Counts for the stat cards. Only active parts are counted."""
    on_hand = quantity_on_hand(user.organization_id)
    status = status_of(func.coalesce(on_hand.c.quantity, 0))
    counts = dict(
        db.execute(
            select(status, func.count())
            .select_from(Part)
            .outerjoin(on_hand, on_hand.c.part_id == Part.id)
            .where(Part.organization_id == user.organization_id, Part.is_active)
            .group_by(status)
        ).all()
    )
    return StockSummary(
        all=sum(counts.values()),
        healthy=counts.get("healthy", 0),
        low=counts.get("low", 0),
        out=counts.get("out", 0),
    )


@router.get("/filters")
def stock_filters(user: User = Depends(anyone), db: Session = Depends(get_session)) -> StockFilters:
    shop = user.organization_id
    categories = db.scalars(
        select(Part.category).where(Part.organization_id == shop, Part.category.is_not(None)).distinct().order_by(Part.category)
    ).all()
    branches = db.execute(select(Branch.id, Branch.name).where(Branch.organization_id == shop).order_by(Branch.created_at))
    suppliers = db.execute(select(Supplier.id, Supplier.name).where(Supplier.organization_id == shop).order_by(Supplier.name))
    return StockFilters(
        categories=list(categories),
        branches=[Choice(id=row.id, name=row.name) for row in branches],
        suppliers=[Choice(id=row.id, name=row.name) for row in suppliers],
    )


@router.get("/parts")
def list_parts(
    search: str | None = None,
    status: StatusFilter | None = None,
    category: str | None = None,
    branch: uuid.UUID | None = None,
    supplier: uuid.UUID | None = None,
    sort: SortKey = "name",
    direction: Literal["asc", "desc"] = "asc",
    page: int = Query(1, ge=1),
    user: User = Depends(anyone),
    db: Session = Depends(get_session),
) -> PartsPage:
    on_hand = quantity_on_hand(user.organization_id, branch)
    quantity = func.coalesce(on_hand.c.quantity, 0)
    part_status = status_of(quantity)

    filters = [Part.organization_id == user.organization_id]
    if search and search.strip():
        term = f"%{_escape_like(search.strip())}%"
        filters.append(or_(Part.name.ilike(term), Part.sku.ilike(term), Part.oem_reference.ilike(term)))
    if status == "dead":
        filters.append(is_dead(quantity, branch))
    elif status:
        filters.append(part_status == status)
    if category:
        filters.append(Part.category == category)
    if supplier:
        filters.append(Part.supplier_id == supplier)

    base = (
        select(Part, quantity.label("quantity"), part_status.label("status"), Supplier.name.label("supplier"))
        .outerjoin(on_hand, on_hand.c.part_id == Part.id)
        .outerjoin(Supplier, Supplier.id == Part.supplier_id)
        .where(*filters)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    order = {
        "name": Part.name,
        "sku": Part.sku,
        "brand": Part.brand,
        "quantity": quantity,
        "min_stock": Part.min_stock,
        "status": _status_rank(part_status),
        "supplier": Supplier.name,
    }[sort]
    ordered = order.desc().nulls_last() if direction == "desc" else order.asc().nulls_last()
    rows = db.execute(base.order_by(ordered, Part.sku).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)).all()

    return PartsPage(
        items=[
            PartRow(
                id=row.Part.id,
                sku=row.Part.sku,
                name=row.Part.name,
                brand=row.Part.brand,
                category=row.Part.category,
                quantity=row.quantity,
                min_stock=row.Part.min_stock,
                status=row.status,
                supplier=row.supplier,
            )
            for row in rows
        ],
        total=total,
        page=page,
        page_size=PAGE_SIZE,
    )


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _status_rank(status):
    """Sorts by urgency: out of stock first, then low, healthy, inactive."""
    return case(*[(status == name, rank) for name, rank in STATUS_ORDER.items()], else_=9)
