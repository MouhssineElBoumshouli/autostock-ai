"""The shop's team. Only owners can see and change it."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import EmailText, NameText, PasswordText, UserOut
from app.audit import record_change
from app.auth.emails import clean_email
from app.auth.passwords import check_password_rules, hash_password
from app.auth.permissions import require_role
from app.auth.sessions import end_all_sessions
from app.db import get_session
from app.models import Role, User

router = APIRouter(prefix="/api/users")
owner_only = require_role("owner")


class NewUser(BaseModel):
    name: NameText
    email: EmailText
    role: Role
    temporary_password: PasswordText


class UserChange(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


@router.get("")
def list_users(owner: User = Depends(owner_only), db: Session = Depends(get_session)) -> list[UserOut]:
    users = db.scalars(
        select(User).where(User.organization_id == owner.organization_id).order_by(User.created_at)
    )
    return [UserOut.of(user) for user in users]


@router.post("", status_code=201)
def add_user(body: NewUser, owner: User = Depends(owner_only), db: Session = Depends(get_session)) -> UserOut:
    email = clean_email(body.email)
    check_password_rules(body.temporary_password)
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "Someone already uses this email.")

    user = User(
        organization_id=owner.organization_id,
        name=body.name,
        email=email,
        password_hash=hash_password(body.temporary_password),
        role=body.role,
    )
    db.add(user)
    db.flush()
    record_change(db, owner, "user.created", "user", user.id, after=user.snapshot())
    db.commit()
    return UserOut.of(user)


@router.patch("/{user_id}")
def change_user(
    user_id: uuid.UUID,
    body: UserChange,
    owner: User = Depends(owner_only),
    db: Session = Depends(get_session),
) -> UserOut:
    user = db.scalar(
        select(User).where(User.id == user_id, User.organization_id == owner.organization_id).with_for_update()
    )
    if user is None:
        raise HTTPException(404, "This person is not in your team.")

    before = user.snapshot()
    stops_being_owner = user.role == "owner" and user.is_active and (
        (body.role is not None and body.role != "owner") or body.is_active is False
    )
    if stops_being_owner and count_active_owners(db, owner.organization_id) <= 1:
        raise HTTPException(409, "The shop needs at least one owner. Make someone else owner first.")

    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
        if not body.is_active:
            end_all_sessions(db, user)

    if user.snapshot() != before:
        record_change(db, owner, "user.updated", "user", user.id, before=before, after=user.snapshot())
    db.commit()
    return UserOut.of(user)


def count_active_owners(db: Session, organization_id: uuid.UUID) -> int:
    # Locks the owner rows so two owners can't remove each other at the same moment.
    owners = db.scalars(
        select(User.id)
        .where(User.organization_id == organization_id, User.role == "owner", User.is_active)
        .with_for_update()
    ).all()
    return len(owners)

