"""The shop's history (audit log), newest first. Owners and managers only."""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.permissions import require_role
from app.db import get_session
from app.models import AuditLog, Organization, User

router = APIRouter(prefix="/api/activity")
can_read_activity = require_role("owner", "manager")

PAGE_SIZE = 25

# Types of change people can filter by, and the audit actions in each.
Kind = Literal["team", "passwords", "logins", "settings", "stock"]
ACTIONS_BY_KIND: dict[str, list[str]] = {
    "team": ["user.created", "user.updated"],
    "passwords": ["user.password_changed", "user.password_reset", "user.password_set_on_shop_computer"],
    "logins": ["user.logged_in"],
    "settings": ["organization.created", "organization.updated", "synonyms.updated"],
    "stock": ["import.saved", "part.updated", "part_equivalent.linked", "part_equivalent.removed"],
}

# Only these fields of before/after are ever sent to the website (never anything secret).
SHOWN_FIELDS = {
    # people and shop
    "name", "email", "role", "is_active", "currency", "order_service_target",
    # parts
    "sku",
    # imports
    "kind", "file_name", "new_parts", "updated_parts", "unchanged_parts", "new_sales", "already_imported",
    "problem_rows", "new_suppliers", "new_branches", "new_equivalents", "already_linked",
    # equivalent part links
    "part", "other_part", "source",
    # merges (branches and suppliers)
    "from", "into",
    # what to order and purchase orders
    "branch", "supplier", "order_number", "quantity", "lines", "cut", "cost", "budget",
    # the "Start here" checklist
    "hidden",
}


class PersonRef(BaseModel):
    id: uuid.UUID
    name: str


class ActivityItem(BaseModel):
    id: uuid.UUID
    created_at: datetime
    action: str
    entity: str
    actor: PersonRef | None
    target: PersonRef | None
    before: dict | None
    after: dict | None


class ActivityPage(BaseModel):
    items: list[ActivityItem]
    total: int
    page: int
    page_size: int


@router.get("")
def list_activity(
    page: int = Query(1, ge=1),
    person: uuid.UUID | None = None,
    kind: Kind | None = None,
    reader: User = Depends(can_read_activity),
    db: Session = Depends(get_session),
) -> ActivityPage:
    filters = [AuditLog.organization_id == reader.organization_id]
    if person:
        filters.append(AuditLog.user_id == person)
    if kind:
        filters.append(AuditLog.action.in_(ACTIONS_BY_KIND[kind]))

    total = db.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0
    rows = db.scalars(
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.created_at.desc(), AuditLog.id)
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).all()
    names = names_in_shop(db, reader.organization_id)

    return ActivityPage(
        items=[describe(row, names) for row in rows],
        total=total,
        page=page,
        page_size=PAGE_SIZE,
    )


@router.get("/people")
def people_in_activity(reader: User = Depends(can_read_activity), db: Session = Depends(get_session)) -> list[PersonRef]:
    """Everyone in the shop, for the "filter by person" list."""
    users = db.scalars(select(User).where(User.organization_id == reader.organization_id).order_by(User.name))
    return [PersonRef(id=user.id, name=user.name) for user in users]


def names_in_shop(db: Session, organization_id: uuid.UUID) -> dict[uuid.UUID, str]:
    users = db.execute(select(User.id, User.name).where(User.organization_id == organization_id)).all()
    organization = db.get_one(Organization, organization_id)
    return {**{user.id: user.name for user in users}, organization.id: organization.name}


def describe(row: AuditLog, names: dict[uuid.UUID, str]) -> ActivityItem:
    def ref(entity_id: uuid.UUID | None) -> PersonRef | None:
        return PersonRef(id=entity_id, name=names[entity_id]) if entity_id in names else None

    return ActivityItem(
        id=row.id,
        created_at=row.created_at,
        action=row.action,
        entity=row.entity,
        actor=ref(row.user_id),
        target=ref(row.entity_id),
        before=shown(row.before),
        after=shown(row.after),
    )


def shown(values: dict | None) -> dict | None:
    if values is None:
        return None
    return {key: value for key, value in values.items() if key in SHOWN_FIELDS}
