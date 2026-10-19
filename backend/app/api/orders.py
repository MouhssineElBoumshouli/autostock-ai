"""What to order: a manager asks for suggestions (optionally within a budget) and reads them back.
Nothing is ever ordered here; approving lines comes in Step 5b."""

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import require_role
from app.db import get_session
from app.models import OrderRun, OrderSuggestion, User
from app.ordering.run import make_order_run

router = APIRouter(prefix="/api/orders")
managers = require_role("owner", "manager")


class SuggestionsRequest(BaseModel):
    budget: int | None = Field(default=None, ge=0)  # centimes; None = no limit


class LineOut(BaseModel):
    part_id: uuid.UUID
    branch_id: uuid.UUID
    supplier_id: uuid.UUID | None
    status: str
    rule: str
    quantity: int
    on_hand: int
    on_order: int
    pack_size: int
    delivery_days: int
    days_covered: int
    expected: float
    cushion: float
    need: int
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


@router.post("/suggestions", status_code=201)
def new_suggestions(body: SuggestionsRequest, user: User = Depends(managers), db: Session = Depends(get_session)) -> RunOut:
    run = make_order_run(db, user, body.budget)
    db.commit()
    return _run_out(db, run)


@router.get("/suggestions/latest")
def latest_suggestions(user: User = Depends(managers), db: Session = Depends(get_session)) -> RunOut | None:
    run = db.scalar(
        select(OrderRun).where(OrderRun.organization_id == user.organization_id).order_by(OrderRun.created_at.desc()).limit(1)
    )
    return _run_out(db, run) if run else None


def _run_out(db: Session, run: OrderRun) -> RunOut:
    lines = db.scalars(
        select(OrderSuggestion)
        .where(OrderSuggestion.organization_id == run.organization_id, OrderSuggestion.run_id == run.id)
        .order_by(OrderSuggestion.status.desc(), OrderSuggestion.value_per_dirham.desc().nulls_first())
    ).all()
    return RunOut(
        **{field: getattr(run, field) for field in RunOut.model_fields if field != "lines"},
        lines=[LineOut.model_validate(line, from_attributes=True) for line in lines],
    )
