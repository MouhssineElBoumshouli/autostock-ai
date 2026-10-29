"""The one permission check. Every protected endpoint uses require_role(...)."""

from collections.abc import Callable

from fastapi import Cookie, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth.sessions import COOKIE_NAME, find_session_user
from app.db import get_session
from app.models import Role, User

MUST_CHANGE_PASSWORD = "Choose a new password first."

# One fixed sentence per role combination actually used (see grep -rn 'require_role(' app/), so
# the message says exactly who can -- "Only the owner can do this.", not a vague refusal. The
# website recognises these exact sentences and shows them in the person's own language
# (frontend/src/i18n/*.ts: serverMessages.fixed).
_NO_ACCESS = {frozenset({"owner"}): "Only the owner can do this.", frozenset({"owner", "manager"}): "Only the owner or a manager can do this."}


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
            raise HTTPException(403, _NO_ACCESS.get(frozenset(allowed), "You don't have access to this."))
        return user

    return check
