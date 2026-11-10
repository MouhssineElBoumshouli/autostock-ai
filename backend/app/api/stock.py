"""The Stock screen: stat cards, filter choices, and the parts list (50 per page)."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import case, func, null, select
from sqlalchemy.orm import Session

from app.api.branches import branches_in_use
from app.auth.permissions import require_role
from app.db import get_session
from app.equivalents import groups_of
from app.models import Branch, Part, StockLevel, Supplier, User
from app.runs_out import (
    RUNNING_OUT_WITHIN_DAYS,
    expected_30d_subquery,
    running_out_status_expr,
    runs_out_days_expr,
    shown_runs_out_days,
)
from app.search.part_search import as_table, find_parts
from app.stock_status import StockStatus, is_dead, quantity_on_hand, status_of

router = APIRouter(prefix="/api/stock")
anyone = require_role()

PAGE_SIZE = 50
StatusFilter = Literal["healthy", "low", "out", "inactive", "dead"]
SortKey = Literal[
    "name", "sku", "brand", "quantity", "min_stock", "status", "supplier", "expected_30d", "runs_out_days", "urgency"
]
STATUS_ORDER = {"out": 0, "low": 1, "running_out": 2, "healthy": 3, "inactive": 4}
NEEDS_ATTENTION = ("out", "low", "running_out")


class StockSummary(BaseModel):
    all: int
    healthy: int
    low: int
    out: int
    running_out: int  # has stock, but expected to run out within RUNNING_OUT_WITHIN_DAYS


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
    expected_30d: int  # pieces expected to sell over the next 30 days
    runs_out_days: int | None  # None means "over 60 days" (or no expected sales at all)
    equivalent_note: EquivalentNote | None = None  # out of stock, but an equivalent from another brand isn't
    zero_branch_name: str | None = None  # "All branches" added up isn't out, but one specific branch is


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
    quantity = func.coalesce(on_hand.c.quantity, 0)
    status = status_of(quantity)
    counts = dict(
        db.execute(
            select(status, func.count())
            .select_from(Part)
            .outerjoin(on_hand, on_hand.c.part_id == Part.id)
            .where(Part.organization_id == user.organization_id, Part.is_active)
            .group_by(status)
        ).all()
    )
    expected = expected_30d_subquery(user.organization_id)
    runs_out = case((expected.c.expected_30d > 0, runs_out_days_expr(quantity, expected.c.expected_30d)), else_=null())
    running_out = db.scalar(
        select(func.count())
        .select_from(Part)
        .outerjoin(on_hand, on_hand.c.part_id == Part.id)
        .outerjoin(expected, expected.c.part_id == Part.id)
        # Already healthy, not already flagged low or out: the minimum didn't catch this one.
        .where(Part.organization_id == user.organization_id, Part.is_active, status == "healthy", runs_out <= RUNNING_OUT_WITHIN_DAYS)
    ) or 0
    return StockSummary(
        all=sum(counts.values()),
        healthy=counts.get("healthy", 0) - running_out,  # some of "healthy" now reads "Running out" instead
        low=counts.get("low", 0),
        out=counts.get("out", 0),
        running_out=running_out,
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
    running_out: bool = False,
    urgent: bool = False,  # only out, low and running-out parts (for the Today page's low stock list)
    sort: SortKey | None = None,
    direction: Literal["asc", "desc"] = "asc",
    page: int = Query(1, ge=1),
    user: User = Depends(anyone),
    db: Session = Depends(get_session),
) -> PartsPage:
    found = find_parts(db, user.organization_id, search) if search and search.strip() else None
    matches = as_table(found.matches) if found else None
    # While searching, stock and forecasts are added up for the matches only, not the whole shop.
    only = select(matches.c.part_id) if found else None
    on_hand = quantity_on_hand(user.organization_id, branch, only)
    quantity = func.coalesce(on_hand.c.quantity, 0)
    part_status = status_of(quantity)
    expected = expected_30d_subquery(user.organization_id, branch, only)
    expected_30d = func.coalesce(expected.c.expected_30d, 0)
    runs_out = case((expected_30d > 0, runs_out_days_expr(quantity, expected_30d)), else_=null())
    final_status = running_out_status_expr(part_status, runs_out)

    filters = [Part.organization_id == user.organization_id]
    if found:
        filters.append(Part.id.in_(only))
    if status == "dead":
        filters.append(is_dead(quantity, branch))
    elif status:
        filters.append(final_status == status)
    if category:
        filters.append(Part.category == category)
    if supplier:
        filters.append(Part.supplier_id == supplier)
    if running_out:
        # Already healthy, not already flagged low or out: the minimum didn't catch this one.
        filters.append(part_status == "healthy")
        filters.append(runs_out <= RUNNING_OUT_WITHIN_DAYS)
    if urgent:
        filters.append(final_status.in_(NEEDS_ATTENTION))

    base = (
        select(
            Part,
            quantity.label("quantity"),
            final_status.label("status"),
            Supplier.name.label("supplier"),
            expected_30d.label("expected_30d"),
            runs_out.label("runs_out_days"),
        )
        .outerjoin(on_hand, on_hand.c.part_id == Part.id)
        .outerjoin(Supplier, Supplier.id == Part.supplier_id)
        .outerjoin(expected, expected.c.part_id == Part.id)
        .where(*filters)
    )
    if matches is not None:
        base = base.join(matches, matches.c.part_id == Part.id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    if sort is None and matches is not None:
        # While searching, the best match comes first unless the person picked a column to sort by.
        ordered = (matches.c.score.desc(),)
    elif sort == "urgency":
        # Out of stock first, then whatever runs out soonest, then the most money at stake
        # (expected sales over the next 30 days, at the sale price): for the Today page's low stock list.
        money_at_stake = expected_30d * func.coalesce(Part.sale_price, Part.unit_cost, 0)
        ordered = (_status_rank(final_status).asc(), runs_out.asc().nulls_last(), money_at_stake.desc().nulls_last())
    else:
        order = {
            "name": Part.name,
            "sku": Part.sku,
            "brand": Part.brand,
            "quantity": quantity,
            "min_stock": Part.min_stock,
            "status": _status_rank(final_status),
            "supplier": Supplier.name,
            "expected_30d": expected_30d,
            "runs_out_days": runs_out,
        }[sort or "name"]
        ordered = (order.desc().nulls_last() if direction == "desc" else order.asc().nulls_last(),)
    rows = db.execute(base.order_by(*ordered, Part.name, Part.sku).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)).all()
    notes = _equivalent_notes(db, user.organization_id, branch, [row.Part.id for row in rows if row.status == "out"])
    zero_branches = _zero_branch_names(
        db, user.organization_id, branch, [row.Part.id for row in rows if row.status != "out"]
    )

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
                expected_30d=round(row.expected_30d),
                runs_out_days=shown_runs_out_days(row.runs_out_days),
                equivalent_note=notes.get(row.Part.id),
                zero_branch_name=zero_branches.get(row.Part.id),
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
    person doesn't have to open the part to find out another brand has it. Only expands from the
    parts actually on screen, so this never slows down as the shop's catalog grows."""
    if not out_of_stock_ids:
        return {}
    groups = groups_of(db, organization_id, out_of_stock_ids)
    candidate_ids = {pid for part_id in out_of_stock_ids for pid in groups.get(part_id, set()) if pid != part_id}
    if not candidate_ids:
        return {}

    on_hand = quantity_on_hand(organization_id, branch)
    quantities = dict(
        db.execute(select(on_hand.c.part_id, on_hand.c.quantity).where(on_hand.c.part_id.in_(candidate_ids))).all()
    )
    names = dict(db.execute(select(Part.id, func.coalesce(Part.brand, Part.name)).where(Part.id.in_(candidate_ids))).all())

    notes: dict[uuid.UUID, EquivalentNote] = {}
    for part_id in out_of_stock_ids:
        others = groups.get(part_id, set()) - {part_id}
        in_stock = [(quantities.get(other) or 0, other) for other in others]
        in_stock = [(qty, other) for qty, other in in_stock if qty > 0]
        if in_stock:
            quantity, best_id = max(in_stock)
            notes[part_id] = EquivalentNote(quantity=quantity, brand=names[best_id])
    return notes


def _zero_branch_names(
    db: Session, organization_id: uuid.UUID, branch_filter: uuid.UUID | None, part_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """"All branches" adds every branch's stock together, so a part can show "Low stock" (or even
    "Healthy") while one specific branch actually has none. Only checked when no single branch is
    already chosen (then its own number already tells the truth), and only for parts not already
    shown as fully out."""
    if branch_filter is not None or not part_ids:
        return {}
    used = branches_in_use(db, organization_id)
    filters = [Branch.organization_id == organization_id]
    if used:
        filters.append(Branch.id.in_(used))
    branches = db.execute(select(Branch.id, Branch.name).where(*filters).order_by(Branch.created_at)).all()
    if len(branches) < 2:
        return {}  # only one branch: "all branches" already means that one

    rows = db.execute(
        select(StockLevel.part_id, StockLevel.branch_id, StockLevel.quantity).where(
            StockLevel.organization_id == organization_id,
            StockLevel.part_id.in_(part_ids),
            StockLevel.branch_id.in_([branch_id for branch_id, _ in branches]),
        )
    ).all()
    quantities = {(part_id, branch_id): quantity for part_id, branch_id, quantity in rows}

    names: dict[uuid.UUID, str] = {}
    for part_id in part_ids:
        per_branch = [quantities.get((part_id, branch_id), 0) for branch_id, _ in branches]
        if sum(per_branch) > 0 and min(per_branch) <= 0:
            names[part_id] = next(name for (_, name), quantity in zip(branches, per_branch) if quantity <= 0)
    return names


def _status_rank(status):
    """Sorts by urgency: out of stock first, then low, healthy, inactive."""
    return case(*[(status == name, rank) for name, rank in STATUS_ORDER.items()], else_=9)
