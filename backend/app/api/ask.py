"""Ask your shop: a question in plain words, answered from the shop's real data. Read-only.

The question is understood by the local model when it is on, else by the keyword rule (see
app/ask). The answer and its numbers always come from the app's own queries, never from the model.
"""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ask.answer_parts import Number
from app.ask.answers import answer
from app.ask.question import QUESTION_TYPES, Question
from app.ask.understand import understand, understand_as
from app.ask.understood_line import heading, understood_line
from app.auth.permissions import require_role
from app.db import get_session
from app.models import Organization, User

router = APIRouter(prefix="/api/ask")
anyone = require_role()

AI_OFF = "AI is off: questions are read with simple keyword rules."
BEST_GUESS = "Best guess. "


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=300)
    question_type: str | None = None  # set by a "Did you mean" button

    @field_validator("question_type")
    @classmethod
    def known_type(cls, value: str | None) -> str | None:
        if value is not None and (value not in QUESTION_TYPES or value == "cannot_answer"):
            raise ValueError("Unknown question type.")
        return value


class Suggestion(BaseModel):
    """A "Did you mean" button: send the same question again with this question_type."""

    question_type: str
    label: str


class AskOut(BaseModel):
    # "I understood: Sales of brake pads · Rabat - Agdal · last month", shown first; starts with
    # "Best guess." when the local model chose the reading, with the other types as buttons below.
    understood: str | None
    question_type: str
    filters: dict[str, str]
    understood_by: Literal["model", "rule"]
    ai_note: str | None  # AI_OFF when the local model isn't running
    sentence: str
    numbers: list[Number]
    suggestions: list[Suggestion]  # when we weren't sure, or the reading is the model's best guess


@router.post("")
def ask(body: AskIn, user: User = Depends(anyone), db: Session = Depends(get_session)) -> AskOut:
    currency = None
    if user.role != "staff":
        currency = db.scalar(select(Organization.currency).where(Organization.id == user.organization_id))
    if body.question_type:
        understood = understand_as(db, user.organization_id, body.question, body.question_type)
    else:
        understood = understand(db, user.organization_id, body.question)
    question = understood.question
    result = answer(db, user.organization_id, question, currency)
    line = understood_line(question)
    if line and understood.understood_by == "model":
        line = BEST_GUESS + line
    return AskOut(
        understood=line,
        question_type=question.type,
        filters=understood.question.filters(),
        understood_by=understood.understood_by,
        ai_note=None if understood.ai_on else AI_OFF,
        sentence=result.sentence,
        numbers=result.numbers,
        suggestions=[_suggestion(question, question_type) for question_type in question.suggestions],
    )


def _suggestion(question: Question, question_type: str) -> Suggestion:
    """Labeled with what was understood so far: "Stock · Rabat - Agdal"."""
    used = QUESTION_TYPES[question_type]
    kept = {name: value for name, value in question.filters().items() if name in used and name != "part"}
    return Suggestion(question_type=question_type, label=heading(Question(question_type, **kept)))
