"""Alerts: the list, and marking one "Looked at it" or "Not a problem" (owners and managers)."""

import uuid
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.alerts.problem import NEEDS_ACTION, SALES_KINDS, WORTH_A_LOOK, group_of
from app.audit import record_change
from app.auth.permissions import require_role
from app.db import get_session, utc_now
from app.models import Alert, Branch, Part, User

router = APIRouter(prefix="/api/alerts")
managers = require_role("owner", "manager")
anyone = require_role()
Reviewer = aliased(User)

Status = Literal["open", "looked_at", "not_a_problem"]
Group = Literal["needs_action", "worth_a_look"]
SHOWN = 200


class AlertOut(BaseModel):
    id: uuid.UUID
    kind: str
    group: Group
    part_id: uuid.UUID
    part_name: str
    sku: str
    branch_name: str
    sentence: str
    numbers: dict
    money_at_stake: int
    started_on: date
    raised_on: date
    status: Status
    reviewed_by: uuid.UUID | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None


class ReviewIn(BaseModel):
    status: Literal["looked_at", "not_a_problem"]


@router.get("")
def list_alerts(
    status: Status | None = None, group: Group | None = None, user: User = Depends(anyone), db: Session = Depends(get_session)
) -> list[AlertOut]:
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
    return [_alert_out(alert, part, branch, reviewer_name) for alert, part, branch, reviewer_name in db.execute(query)]


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
    return _alert_out(alert, part, branch, user.name)


def _alert_out(alert: Alert, part: Part, branch: Branch, reviewer_name: str | None) -> AlertOut:
    return AlertOut(
        **{field: getattr(alert, field) for field in AlertOut.model_fields if hasattr(alert, field)},
        part_name=part.name,
        sku=part.sku,
        branch_name=branch.name,
        group=group_of(alert.kind),
        reviewed_by_name=reviewer_name,
    )
