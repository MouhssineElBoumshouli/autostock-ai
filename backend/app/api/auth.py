"""Log in, log out, and "who am I"."""

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import EmailText, Me, OrganizationOut, PasswordText, UserOut
from app.audit import record_change
from app.auth import login_limits
from app.auth.passwords import password_matches
from app.auth.permissions import require_role
from app.auth.sessions import COOKIE_NAME, end_session, start_session
from app.db import get_session, utc_now
from app.models import Organization, User

router = APIRouter(prefix="/api/auth")

WRONG_LOGIN = "Wrong email or password."
TOO_MANY_TRIES = "Too many tries. Wait 15 minutes."
ACCOUNT_OFF = "This account is turned off. Ask your shop owner."


class LoginRequest(BaseModel):
    email: EmailText
    password: PasswordText


def describe_me(db: Session, user: User) -> Me:
    organization = db.get_one(Organization, user.organization_id)
    return Me(user=UserOut.of(user), organization=OrganizationOut(id=organization.id, name=organization.name))


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_session)) -> Me:
    email = body.email.strip().lower()
    if login_limits.is_blocked(db, email):
        raise HTTPException(429, TOO_MANY_TRIES)

    user = db.scalar(select(User).where(User.email == email))
    if not password_matches(user.password_hash if user else None, body.password):
        login_limits.record_failure(db, email, user.organization_id if user else None)
        raise HTTPException(401, WRONG_LOGIN)
    if not user.is_active:
        raise HTTPException(403, ACCOUNT_OFF)

    login_limits.clear_failures(db, email)
    user.last_login_at = utc_now()
    record_change(db, user, "user.logged_in", "user", user.id)
    start_session(db, user, response)
    db.commit()
    return describe_me(db, user)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    db: Session = Depends(get_session),
    token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> None:
    end_session(db, token, response)


@router.get("/me")
def me(user: User = Depends(require_role()), db: Session = Depends(get_session)) -> Me:
    return describe_me(db, user)

