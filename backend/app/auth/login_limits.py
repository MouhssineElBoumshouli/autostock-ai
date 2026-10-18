"""Slows down password guessing: 5 wrong logins for one email within 15 minutes blocks it for 15 minutes."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import utc_now
from app.models import LoginFailure

MAX_FAILURES = 5
WINDOW = timedelta(minutes=15)
BLOCK_TIME = timedelta(minutes=15)


def is_blocked(db: Session, email: str, now: datetime | None = None) -> bool:
    now = now or utc_now()
    recent = db.scalars(
        select(LoginFailure.created_at)
        .where(LoginFailure.email == email, LoginFailure.created_at > now - WINDOW - BLOCK_TIME)
        .order_by(LoginFailure.created_at.desc())
        .limit(MAX_FAILURES)
    ).all()
    if len(recent) < MAX_FAILURES:
        return False
    newest, oldest = recent[0], recent[-1]
    return newest - oldest <= WINDOW and now < newest + BLOCK_TIME


def record_failure(db: Session, email: str, organization_id: uuid.UUID | None) -> None:
    db.add(LoginFailure(email=email, organization_id=organization_id))
    db.commit()


def clear_failures(db: Session, email: str) -> None:
    db.execute(delete(LoginFailure).where(LoginFailure.email == email))
