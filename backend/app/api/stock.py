"""The Stock screen: stat cards, filter choices, and the parts list (50 per page)."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.auth.permissions import require_role
from app.db import get_session
from app.equivalents import load_graph, reachable_from
from app.models import Branch, Part, Supplier, User
from app.search.part_search import as_table, find_parts
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


class EquivalentNote(BaseModel):
    quantity: int
    brand: str  # the other part's brand, or its name when it has none


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
    equivalent_note: EquivalentNote | None = None  # out of stock, but an equivalent from another brand isn't


class PartsPage(BaseModel):
    items: list[PartRow]
    total: int
    page: int
    page_size: int
    closest: bool = False  # the search matched nothing well; these are the closest parts


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
    sort: SortKey | None = None,
    direction: Literal["asc", "desc"] = "asc",
    page: int = Query(1, ge=1),
    user: User = Depends(anyone),
    db: Session = Depends(get_session),
) -> PartsPage:
    on_hand = quantity_on_hand(user.organization_id, branch)
    quantity = func.coalesce(on_hand.c.quantity, 0)
    part_status = status_of(quantity)

    filters = [Part.organization_id == user.organization_id]
    found = find_parts(db, user.organization_id, search) if search and search.strip() else None
    matches = as_table(found.matches) if found else None
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
    if matches is not None:
        base = base.join(matches, matches.c.part_id == Part.id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    if sort is None and matches is not None:
        # While searching, the best match comes first unless the person picked a column to sort by.
        ordered = matches.c.score.desc()
    else:
        order = {
            "name": Part.name,
            "sku": Part.sku,
            "brand": Part.brand,
            "quantity": quantity,
            "min_stock": Part.min_stock,
            "status": _status_rank(part_status),
            "supplier": Supplier.name,
        }[sort or "name"]
        ordered = order.desc().nulls_last() if direction == "desc" else order.asc().nulls_last()
    rows = db.execute(base.order_by(ordered, Part.name, Part.sku).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)).all()
    notes = _equivalent_notes(db, user.organization_id, branch, [row.Part.id for row in rows if row.status == "out"])

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
                equivalent_note=notes.get(row.Part.id),
            )
            for row in rows
        ],
        total=total,
        page=page,
        page_size=PAGE_SIZE,
        closest=bool(found and found.closest),
    )


def _equivalent_notes(
    db: Session, organization_id: uuid.UUID, branch: uuid.UUID | None, out_of_stock_ids: list[uuid.UUID]
) -> dict[uuid.UUID, EquivalentNote]:
    """For each out-of-stock part shown, the best equivalent that IS in stock (most on hand), so the
    person doesn't have to open the part to find out another brand has it."""
    if not out_of_stock_ids:
        return {}
    graph = load_graph(db, organization_id)
    reached_by_part = {part_id: reachable_from(graph, part_id) for part_id in out_of_stock_ids}
    candidate_ids = {r.part_id for reached in reached_by_part.values() for r in reached}
    if not candidate_ids:
        return {}

    on_hand = quantity_on_hand(organization_id, branch)
    quantities = dict(
        db.execute(select(on_hand.c.part_id, on_hand.c.quantity).where(on_hand.c.part_id.in_(candidate_ids))).all()
    )
    names = dict(db.execute(select(Part.id, func.coalesce(Part.brand, Part.name)).where(Part.id.in_(candidate_ids))).all())

    notes: dict[uuid.UUID, EquivalentNote] = {}
    for part_id, reached in reached_by_part.items():
        in_stock = [(quantities.get(r.part_id) or 0, r.part_id) for r in reached]
        in_stock = [(qty, pid) for qty, pid in in_stock if qty > 0]
        if in_stock:
            quantity, best_id = max(in_stock)
            notes[part_id] = EquivalentNote(quantity=quantity, brand=names[best_id])
    return notes


def _status_rank(status):
    """Sorts by urgency: out of stock first, then low, healthy, inactive."""
    return case(*[(status == name, rank) for name, rank in STATUS_ORDER.items()], else_=9)
