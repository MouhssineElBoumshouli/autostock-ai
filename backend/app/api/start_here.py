"""The "Start here" checklist a new shop sees on Today instead of empty sections: five steps,
each ticked from real data (never by a click), so it always shows the shop's true state. Owners
and managers only -- staff can't do any of these things anyway.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.audit import record_change
from app.auth.permissions import require_role
from app.db import get_session
from app.models import Branch, Organization, Part, SaleLine, Supplier, User

router = APIRouter(prefix="/api/start-here")
managers = require_role("owner", "manager")

StepKey = Literal["branches", "import_parts", "import_sales", "suppliers", "team"]
STEP_KEYS: tuple[StepKey, ...] = ("branches", "import_parts", "import_sales", "suppliers", "team")


class StartHereStep(BaseModel):
    key: StepKey
    done: bool


class StartHereOut(BaseModel):
    hidden: bool
    all_done: bool
    steps: list[StartHereStep]


class StartHereChange(BaseModel):
    hidden: bool


def _branches_checked(db: Session, organization_id: uuid.UUID, organization_name: str) -> bool:
    """More than the one branch every shop starts with, or that one was given its own name."""
    branches = db.scalars(select(Branch).where(Branch.organization_id == organization_id)).all()
    return len(branches) > 1 or any(branch.name != organization_name for branch in branches)


def _done_steps(db: Session, organization_id: uuid.UUID) -> dict[StepKey, bool]:
    organization_name = db.scalar(select(Organization.name).where(Organization.id == organization_id)) or ""
    team_size = db.scalar(
        select(func.count()).select_from(User).where(User.organization_id == organization_id, User.is_active)
    ) or 0
    return {
        "branches": _branches_checked(db, organization_id, organization_name),
        "import_parts": bool(db.scalar(select(exists().where(Part.organization_id == organization_id)))),
        "import_sales": bool(db.scalar(select(exists().where(SaleLine.organization_id == organization_id)))),
        "suppliers": bool(
            db.scalar(select(exists().where(Supplier.organization_id == organization_id, Supplier.delivery_days.is_not(None))))
        ),
        "team": team_size > 1,
    }


def _out(db: Session, organization_id: uuid.UUID, hidden: bool) -> StartHereOut:
    done = _done_steps(db, organization_id)
    return StartHereOut(
        hidden=hidden, all_done=all(done.values()), steps=[StartHereStep(key=key, done=done[key]) for key in STEP_KEYS]
    )


@router.get("")
def read_start_here(user: User = Depends(managers), db: Session = Depends(get_session)) -> StartHereOut:
    hidden = bool(db.scalar(select(Organization.start_here_hidden).where(Organization.id == user.organization_id)))
    return _out(db, user.organization_id, hidden)


@router.patch("")
def change_start_here(
    body: StartHereChange, user: User = Depends(managers), db: Session = Depends(get_session)
) -> StartHereOut:
    organization = db.get_one(Organization, user.organization_id, with_for_update=True)
    before = organization.start_here_hidden
    organization.start_here_hidden = body.hidden
    if organization.start_here_hidden != before:
        record_change(
            db, user, "start_here.hidden_changed", "organization", organization.id,
            before={"hidden": before}, after={"hidden": organization.start_here_hidden},
        )
    db.commit()
    return _out(db, user.organization_id, organization.start_here_hidden)
