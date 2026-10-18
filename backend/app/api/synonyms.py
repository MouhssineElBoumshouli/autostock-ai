"""The shop's search word list: groups of words that mean the same part. Owners can edit it."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.audit import record_change
from app.auth.permissions import require_role
from app.db import get_session
from app.models import SynonymGroup, User

router = APIRouter(prefix="/api/synonyms")
owner_only = require_role("owner")

Word = Annotated[str, Field(max_length=100)]


class SynonymList(BaseModel):
    groups: list[Annotated[list[Word], Field(max_length=30)]] = Field(max_length=500)


def read_groups(db: Session, user: User) -> list[list[str]]:
    """In alphabetical order, so the list always reads the same way."""
    rows = db.scalars(select(SynonymGroup.words).where(SynonymGroup.organization_id == user.organization_id))
    return sorted((list(words) for words in rows), key=_sort_key)


def _sort_key(words: list[str]) -> list[str]:
    return [word.lower() for word in words]


def clean_groups(groups: list[list[str]]) -> list[list[str]]:
    """Trims words, drops empty and repeated ones. A group needs at least two words to mean anything."""
    cleaned = []
    for group in groups:
        words: list[str] = []
        for word in group:
            word = " ".join(word.split())
            if word and word.lower() not in (known.lower() for known in words):
                words.append(word)
        if len(words) >= 2:
            cleaned.append(words)
    return sorted(cleaned, key=_sort_key)


@router.get("")
def list_synonyms(owner: User = Depends(owner_only), db: Session = Depends(get_session)) -> SynonymList:
    return SynonymList(groups=read_groups(db, owner))


@router.put("")
def replace_synonyms(body: SynonymList, owner: User = Depends(owner_only), db: Session = Depends(get_session)) -> SynonymList:
    before = read_groups(db, owner)
    after = clean_groups(body.groups)
    if not after and body.groups:
        raise HTTPException(422, "Each line needs at least two words, separated by commas.")
    if after != before:
        db.execute(delete(SynonymGroup).where(SynonymGroup.organization_id == owner.organization_id))
        db.flush()
        db.add_all(SynonymGroup(organization_id=owner.organization_id, words=words) for words in after)
        record_change(db, owner, "synonyms.updated", "organization", owner.organization_id,
                      before={"groups": before}, after={"groups": after})
    db.commit()
    return SynonymList(groups=read_groups(db, owner))
