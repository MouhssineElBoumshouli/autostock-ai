"""Writes one audit_log row for every change to business data."""

import uuid

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def record_change(
    db: Session,
    actor: User,
    action: str,
    entity: str,
    entity_id: uuid.UUID,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            organization_id=actor.organization_id,
            user_id=actor.id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            before=before,
            after=after,
        )
    )
