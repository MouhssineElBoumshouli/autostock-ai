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
from app.models import Branch, Organization, SynonymGroup, User
from app.search.default_synonyms import DEFAULT_SYNONYMS

router = APIRouter(prefix="/api/setup")


class SetupStatus(BaseModel):
    needed: bool


class SetupRequest(BaseModel):
    shop_name: NameText
    name: NameText
    email: EmailText
    password: PasswordText


def anyone_exists(db: Session) -> bool:
    """Someone in a real shop. The demo shop's account does not count, so setup still runs."""
    real_user = select(User.id).join(Organization, Organization.id == User.organization_id).where(~Organization.is_demo)
    return db.scalar(select(exists(real_user))) or False


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

    organization = Organization(name=body.shop_name, currency="MAD")
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
    # Every shop starts with one branch, named after the shop.
    db.add(Branch(organization_id=organization.id, name=organization.name))
    db.add_all(SynonymGroup(organization_id=organization.id, words=words) for words in DEFAULT_SYNONYMS)
    db.flush()
    # One activity line for the whole setup: "Sara created the shop Atlas Parts."
    record_change(
        db,
        owner,
        "organization.created",
        "organization",
        organization.id,
        after={"name": organization.name, "currency": organization.currency, "owner": owner.snapshot()},
    )
    start_session(db, owner, response)
    db.commit()
    return describe_me(db, owner)
