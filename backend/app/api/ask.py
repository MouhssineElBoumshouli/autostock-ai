"""Ask your shop: a question in plain words, answered from the shop's real data. Read-only.

The question is understood by the local model when it is on, else by the keyword rule (see
app/ask). The answer and its numbers always come from the app's own queries, never from the model.
"""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ask.answer_parts import Number
from app.ask.answers import answer
from app.ask.understand import understand
from app.auth.permissions import require_role
from app.db import get_session
from app.models import Organization, User

router = APIRouter(prefix="/api/ask")
anyone = require_role()

AI_OFF = "AI is off: questions are read with simple keyword rules."


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=300)


class AskOut(BaseModel):
    question_type: str
    filters: dict[str, str]
    understood_by: Literal["model", "rule"]
    ai_note: str | None  # AI_OFF when the local model isn't running
    sentence: str
    numbers: list[Number]


@router.post("")
def ask(body: AskIn, user: User = Depends(anyone), db: Session = Depends(get_session)) -> AskOut:
    currency = None
    if user.role != "staff":
        currency = db.scalar(select(Organization.currency).where(Organization.id == user.organization_id))
    understood = understand(db, user.organization_id, body.question)
    result = answer(db, user.organization_id, understood.question, currency)
    return AskOut(
        question_type=understood.question.type,
        filters=understood.question.filters(),
        understood_by=understood.understood_by,
        ai_note=None if understood.ai_on else AI_OFF,
        sentence=result.sentence,
        numbers=result.numbers,
    )
