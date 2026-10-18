"""First-time setup: creates the shop and its first owner. Closed forever once anyone exists."""

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import exists, select, text
from sqlalchemy.orm import Session

from app.api.auth import describe_me
from app.api.schemas import EmailText, Me, NameText, PasswordText
from app.audit import record_change
from app.auth.emails import clean_email
from app.auth.passwords import check_password_rules, hash_password
from app.auth.sessions import start_session
from app.db import get_session, utc_now
from app.models import Organization, User

router = APIRouter(prefix="/api/setup")


class SetupStatus(BaseModel):
    needed: bool


class SetupRequest(BaseModel):
    shop_name: NameText
    name: NameText
    email: EmailText
    password: PasswordText


def anyone_exists(db: Session) -> bool:
    return db.scalar(select(exists().select_from(User))) or False


@router.get("")
def setup_status(db: Session = Depends(get_session)) -> SetupStatus:
    return SetupStatus(needed=not anyone_exists(db))


@router.post("", status_code=201)
def run_setup(body: SetupRequest, response: Response, db: Session = Depends(get_session)) -> Me:
    email = clean_email(body.email)
    check_password_rules(body.password)

    # Only one setup can run at a time, so two people can't both become the first owner.
    db.execute(text("SELECT pg_advisory_xact_lock(1)"))
    if anyone_exists(db):
        raise HTTPException(409, "This shop is already set up. Log in instead.")

    organization = Organization(name=body.shop_name)
    db.add(organization)
    db.flush()
    owner = User(
        organization_id=organization.id,
        name=body.name,
        email=email,
        password_hash=hash_password(body.password),
        role="owner",
        last_login_at=utc_now(),
    )
    db.add(owner)
    db.flush()
    record_change(db, owner, "organization.created", "organization", organization.id, after={"name": organization.name})
    record_change(db, owner, "user.created", "user", owner.id, after=owner.snapshot())
    start_session(db, owner, response)
    db.commit()
    return describe_me(db, owner)
