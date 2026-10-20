"""Alerts: the list, and marking one "Looked at it" or "Not a problem" (owners and managers)."""

import uuid
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.alerts.problem import NEEDS_ACTION, SALES_KINDS, WORTH_A_LOOK, group_of, money_note
from app.audit import record_change
from app.auth.permissions import require_role
from app.db import get_session, utc_now
from app.models import Alert, Branch, Organization, Part, User

router = APIRouter(prefix="/api/alerts")
managers = require_role("owner", "manager")
anyone = require_role()
Reviewer = aliased(User)

Status = Literal["open", "looked_at", "not_a_problem"]
Group = Literal["needs_action", "worth_a_look"]
SHOWN = 200


class AlertBase(BaseModel):
    """What everyone sees, staff included: no money. See AlertOut."""

    id: uuid.UUID
    kind: str
    group: Group
    part_id: uuid.UUID
    part_name: str
    sku: str
    branch_name: str
    sentence: str
    numbers: dict
    started_on: date
    raised_on: date
    status: Status
    reviewed_by: uuid.UUID | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None


class AlertOut(AlertBase):
    """Owners and managers also see the money at stake, and the sentence says it too."""

    money_at_stake: int


class ReviewIn(BaseModel):
    status: Literal["looked_at", "not_a_problem"]


@router.get("")
def list_alerts(
    status: Status | None = None, group: Group | None = None, user: User = Depends(anyone), db: Session = Depends(get_session)
) -> list[AlertOut] | list[AlertBase]:
    """Newest first; within a day, the most money at stake first. `group`: "needs_action" (stock
    that doesn't match sales) or "worth_a_look" (sales spikes and drops)."""
    query = (
        select(Alert, Part, Branch, Reviewer.name)
        .join(Part, Part.id == Alert.part_id)
        .join(Branch, Branch.id == Alert.branch_id)
        .outerjoin(Reviewer, Reviewer.id == Alert.reviewed_by)
        .where(Alert.organization_id == user.organization_id)
        .order_by(Alert.raised_on.desc(), Alert.money_at_stake.desc())
        .limit(SHOWN)
    )
    if status:
        query = query.where(Alert.status == status)
    if group == WORTH_A_LOOK:
        query = query.where(Alert.kind.in_(SALES_KINDS))
    elif group == NEEDS_ACTION:
        query = query.where(Alert.kind.not_in(SALES_KINDS))
    can_see_money = user.role != "staff"
    currency = _currency(db, user.organization_id) if can_see_money else None
    return [
        _alert_out(alert, part, branch, reviewer_name, currency)
        for alert, part, branch, reviewer_name in db.execute(query)
    ]


@router.post("/{alert_id}/review")
def review(alert_id: uuid.UUID, body: ReviewIn, user: User = Depends(managers), db: Session = Depends(get_session)) -> AlertOut:
    alert = db.scalar(select(Alert).where(Alert.id == alert_id, Alert.organization_id == user.organization_id).with_for_update())
    if alert is None:
        raise HTTPException(404, "This alert is not in your shop.")
    part, branch = db.get(Part, alert.part_id), db.get(Branch, alert.branch_id)
    before = alert.status
    alert.status, alert.reviewed_by, alert.reviewed_at = body.status, user.id, utc_now()
    after = {"status": body.status, "kind": alert.kind, "part": part.name, "branch": branch.name}
    record_change(db, user, "alert.reviewed", "alert", alert.id, before={"status": before}, after=after)
    db.commit()
    return _alert_out(alert, part, branch, user.name, _currency(db, user.organization_id))


def _currency(db: Session, organization_id: uuid.UUID) -> str:
    return db.scalar(select(Organization.currency).where(Organization.id == organization_id))


def _alert_out(alert: Alert, part: Part, branch: Branch, reviewer_name: str | None, currency: str | None) -> AlertOut | AlertBase:
    fields = dict(
        id=alert.id, kind=alert.kind, group=group_of(alert.kind), part_id=alert.part_id, part_name=part.name,
        sku=part.sku, branch_name=branch.name, numbers=alert.numbers, started_on=alert.started_on,
        raised_on=alert.raised_on, status=alert.status, reviewed_by=alert.reviewed_by,
        reviewed_by_name=reviewer_name, reviewed_at=alert.reviewed_at,
    )
    if currency is None:
        return AlertBase(**fields, sentence=alert.sentence)
    sentence = f"{alert.sentence} {money_note(alert.kind, alert.money_at_stake, currency)}"
    return AlertOut(**fields, sentence=sentence, money_at_stake=alert.money_at_stake)
