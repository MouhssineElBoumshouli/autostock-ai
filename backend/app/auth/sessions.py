"""Login sessions: a random token in an HttpOnly cookie, only its hash in the database."""

import hashlib
import secrets
from datetime import timedelta

from fastapi import Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import COOKIES_SECURE
from app.db import utc_now
from app.models import User, UserSession

COOKIE_NAME = "autostock_session"
IDLE_LIMIT = timedelta(days=7)
# Saving "last used" on every request is wasteful; once every few minutes is enough.
TOUCH_INTERVAL = timedelta(minutes=5)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(db: Session, user: User, response: Response) -> None:
    token = secrets.token_urlsafe(32)
    db.add(UserSession(organization_id=user.organization_id, user_id=user.id, token_hash=_hash_token(token)))
    _set_cookie(response, token)


def find_session_user(db: Session, token: str | None, response: Response) -> User | None:
    """Returns the logged-in user for this cookie, or None if it is missing, expired or turned off."""
    if not token:
        return None
    found = db.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(UserSession.token_hash == _hash_token(token))
    ).first()
    if found is None:
        return None
    user_session, user = found
    now = utc_now()
    if now - user_session.last_used_at > IDLE_LIMIT or not user.is_active:
        db.delete(user_session)
        db.commit()
        return None
    if now - user_session.last_used_at > TOUCH_INTERVAL:
        user_session.last_used_at = now
        db.commit()
        _set_cookie(response, token)
    return user


def end_session(db: Session, token: str | None, response: Response) -> None:
    if token:
        db.execute(delete(UserSession).where(UserSession.token_hash == _hash_token(token)))
        db.commit()
    response.delete_cookie(COOKIE_NAME, httponly=True, samesite="lax", secure=COOKIES_SECURE)


def end_all_sessions(db: Session, user: User) -> None:
    db.execute(delete(UserSession).where(UserSession.user_id == user.id))


def end_other_sessions(db: Session, user: User, current_token: str) -> None:
    """Logs the person out on every other browser, keeps this one."""
    db.execute(
        delete(UserSession).where(
            UserSession.user_id == user.id, UserSession.token_hash != _hash_token(current_token)
        )
    )


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(IDLE_LIMIT.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=COOKIES_SECURE,
    )
