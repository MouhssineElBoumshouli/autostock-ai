"""Shop settings: name, currency and default language. Only owners can see and change them."""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.schemas import NameText
from app.audit import record_change
from app.auth.permissions import require_role
from app.db import get_session
from app.models import Language, Organization, User

router = APIRouter(prefix="/api/settings")
owner_only = require_role("owner")

Currency = Literal["MAD", "EUR", "USD"]


class ShopSettings(BaseModel):
    name: str
    currency: Currency
    language: Language


class SettingsChange(BaseModel):
    name: NameText | None = None
    currency: Currency | None = None
    language: Language | None = None


def snapshot(organization: Organization) -> dict:
    return {"name": organization.name, "currency": organization.currency, "language": organization.language}


@router.get("")
def read_settings(owner: User = Depends(owner_only), db: Session = Depends(get_session)) -> ShopSettings:
    return ShopSettings(**snapshot(db.get_one(Organization, owner.organization_id)))


@router.patch("")
def change_settings(
    body: SettingsChange,
    owner: User = Depends(owner_only),
    db: Session = Depends(get_session),
) -> ShopSettings:
    organization = db.get_one(Organization, owner.organization_id, with_for_update=True)
    before = snapshot(organization)
    if body.name is not None:
        organization.name = body.name
    if body.currency is not None:
        organization.currency = body.currency
    if body.language is not None:
        organization.language = body.language

    if snapshot(organization) != before:
        record_change(
            db, owner, "organization.updated", "organization", organization.id, before=before, after=snapshot(organization)
        )
    db.commit()
    return ShopSettings(**snapshot(organization))
