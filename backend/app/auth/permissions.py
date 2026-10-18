"""The one permission check. Every protected endpoint uses require_role(...)."""

from collections.abc import Callable

from fastapi import Cookie, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth.sessions import COOKIE_NAME, find_session_user
from app.db import get_session
from app.models import Role, User


def require_role(*allowed: Role) -> Callable[..., User]:
    """Use as `user: User = Depends(require_role("owner"))`. No roles given = any logged-in person."""

    def check(
        response: Response,
        db: Session = Depends(get_session),
        token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> User:
        user = find_session_user(db, token, response)
        if user is None:
            raise HTTPException(401, "Please log in.")
        if allowed and user.role not in allowed:
            raise HTTPException(403, "You don't have access to this.")
        return user

    return check
