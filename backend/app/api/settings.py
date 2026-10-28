"""Shop settings: name, currency, default language and the optional cloud writer. Only owners can see and change them."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai import cloud_writer
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
    cloud_writer_on: bool
    cloud_writer_ready: bool  # a Groq key is set (.env): only then can the cloud writer be turned on


class SettingsChange(BaseModel):
    name: NameText | None = None
    currency: Currency | None = None
    language: Language | None = None
    cloud_writer_on: bool | None = None


NO_GROQ_KEY = "Add GROQ_API_KEY to the .env file first."


def snapshot(organization: Organization) -> dict:
    return {"name": organization.name, "currency": organization.currency, "language": organization.language,
            "cloud_writer_on": organization.cloud_writer_on}


def shown(organization: Organization) -> ShopSettings:
    return ShopSettings(**snapshot(organization), cloud_writer_ready=cloud_writer.is_ready())


@router.get("")
def read_settings(owner: User = Depends(owner_only), db: Session = Depends(get_session)) -> ShopSettings:
    return shown(db.get_one(Organization, owner.organization_id))


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
    if body.cloud_writer_on is not None:
        if body.cloud_writer_on and not cloud_writer.is_ready():
            raise HTTPException(422, NO_GROQ_KEY)
        organization.cloud_writer_on = body.cloud_writer_on

    if snapshot(organization) != before:
        record_change(
            db, owner, "organization.updated", "organization", organization.id, before=before, after=snapshot(organization)
        )
    db.commit()
    return shown(organization)
