"""The one permission check. Every protected endpoint uses require_role(...)."""

from collections.abc import Callable

from fastapi import Cookie, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth.sessions import COOKIE_NAME, find_session_user
from app.db import get_session
from app.models import Role, User

MUST_CHANGE_PASSWORD = "Choose a new password first."


def require_role(*allowed: Role, before_password_change: bool = False) -> Callable[..., User]:
    """Use as `user: User = Depends(require_role("owner"))`. No roles given = any logged-in person.

    People whose password was set by the owner are blocked until they choose their own,
    except on the few endpoints marked `before_password_change=True`.
    """

    def check(
        response: Response,
        db: Session = Depends(get_session),
        token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> User:
        user = find_session_user(db, token, response)
        if user is None:
            raise HTTPException(401, "Please log in.")
        if user.must_change_password and not before_password_change:
            raise HTTPException(403, MUST_CHANGE_PASSWORD)
        if allowed and user.role not in allowed:
            raise HTTPException(403, "You don't have access to this.")
        return user

    return check
