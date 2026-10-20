"""Writes one audit_log row for every change to business data."""

import uuid

from sqlalchemy.orm import Session

from app.models import AuditLog, User

# Every action name any `record_change` call uses, anywhere in the backend. A test
# (tests/test_audit_actions.py) scans the code and fails if one is used here without being
# added to this list — so a new kind of change can't reach the Activity page without someone
# also giving it a plain sentence in activitySentence.ts and i18n/en.ts.
KNOWN_ACTIONS = frozenset({
    "organization.created",
    "organization.updated",
    "synonyms.updated",
    "user.created",
    "user.updated",
    "user.logged_in",
    "user.password_changed",
    "user.password_reset",
    "branch.renamed",
    "branch.merged",
    "branch.removed",
    "supplier.renamed",
    "supplier.merged",
    "supplier.removed",
    "import.saved",
    "part.updated",
    "part_equivalent.linked",
    "part_equivalent.removed",
    "forecast.requested",
    "order_suggestions.created",
    "order_suggestion.approved",
    "order_suggestion.rejected",
    "purchase_order.created",
    "purchase_order.sent",
    "purchase_order.received",
    "stock_level.received",
    "alert.reviewed",
})


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
