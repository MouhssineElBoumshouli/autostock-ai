"""Ask your shop: a question in plain words, answered from the shop's real data. Read-only.

With the local model on, POST /api/ask/chat: the model reads the question, the app looks things up and
writes the answer (or the optional cloud writer, checked against the data; app/ask/assistant.py).
With AI off, POST /api/ask: the keyword rule reads the question and the app writes the answer.
Both are written in the question's language and saved in the person's history (GET /api/ask/history).
"""

import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import cloud_writer, llm
from app.ask.answer_parts import Number
from app.ask.answers import answer
from app.ask.assistant import as_line, converse
from app.ask.history import forget, recent, remember
from app.ask.question import QUESTION_TYPES, Question, checked_question
from app.ask.reply_language import reply_language
from app.ask.sentences import written_answer
from app.ask.understand import shop_words, understand, understand_as
from app.ask.understood_line import heading, shown_period, understood_line
from app.auth.permissions import require_role
from app.db import SessionLocal, get_session
from app.models import Organization, User

router = APIRouter(prefix="/api/ask")
anyone = require_role()

AI_OFF = "AI is off: questions are read with simple keyword rules."
BEST_GUESS = "Best guess. "


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=300)
    question_type: str | None = None  # set by a "Did you mean" button, or to keep the type while changing a filter
    filters: dict[str, str] | None = None  # set by a filter chip: replaces the filters for question_type

    @field_validator("question_type")
    @classmethod
    def known_type(cls, value: str | None) -> str | None:
        if value is not None and (value not in QUESTION_TYPES or value == "cannot_answer"):
            raise ValueError("Unknown question type.")
        return value


class Suggestion(BaseModel):
    """A "Did you mean" button: send the same question again with this question_type."""

    question_type: str
    label: str  # English; the website builds it from the type, filters and period
    filters: dict[str, str]
    period: str | None


class AskOut(BaseModel):
    # "I understood: Sales of brake pads · Rabat - Agdal · last month", shown first; starts with
    # "Best guess." when the local model chose the reading, with the other types as buttons below.
    understood: str | None
    question_type: str
    filters: dict[str, str]
    understood_by: Literal["model", "rule"]
    ai_note: str | None  # AI_OFF when the local model isn't running
    ai_on: bool
    period: str | None  # the period the "I understood" line shows, if this question type takes one
    # `understood` is English; the website builds it in the person's language from the type, filters and
    # period above (frontend/src/i18n). `answer` is written by the app in the question's own language.
    key: str
    values: dict
    answer: str
    language: str  # "en", "fr" or "ar": the language `answer` is written in
    numbers: list[Number]
    suggestions: list[Suggestion]  # when we weren't sure, or the reading is the model's best guess


class AskedBefore(BaseModel):
    """The question before in this conversation, as the app understood it (sent back by the website)."""

    type: str
    filters: dict[str, str] = {}


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=300)
    previous: AskedBefore | None = None  # so "and in Rabat?" or "why?" can change it


class AskedOut(BaseModel):
    """One earlier question and the answer the page showed: `answer` is the assistant's "done" event
    (kind "assistant") or an AskOut (kind "rule")."""

    id: str
    question: str
    kind: str
    answer: dict


def app_language(db: Session, user: User) -> str:
    """The language the person sees the app in: their own choice, else the shop's."""
    return user.language or db.scalar(select(Organization.language).where(Organization.id == user.organization_id))


def cloud_on(db: Session, user: User) -> bool:
    """The owner turned the cloud writer on, and a Groq key is set."""
    turned_on = db.scalar(select(Organization.cloud_writer_on).where(Organization.id == user.organization_id))
    return bool(turned_on) and cloud_writer.is_ready()


def currency_seen(db: Session, user: User) -> str | None:
    """The shop's currency, or None for people who don't see money."""
    if user.role == "staff":
        return None
    return db.scalar(select(Organization.currency).where(Organization.id == user.organization_id))


@router.get("/history")
def history(user: User = Depends(anyone), db: Session = Depends(get_session)) -> list[AskedOut]:
    """The person's last questions and answers, oldest first."""
    return [AskedOut(id=str(asked.id), question=asked.question, kind=asked.kind, answer=asked.answer) for asked in recent(db, user)]


@router.delete("/history", status_code=204)
def clear_history(user: User = Depends(anyone), db: Session = Depends(get_session)) -> None:
    """"Clear history" (after a confirm): the person's earlier questions are forgotten."""
    forget(db, user)


@router.get("/ai")
def ai(user: User = Depends(anyone)) -> dict[str, bool]:
    """Whether the local AI is running, so the page can say up front when it isn't."""
    return {"ai_on": llm.is_on()}


@router.post("/chat")
def chat(body: ChatIn, user: User = Depends(anyone), db: Session = Depends(get_session)) -> StreamingResponse:
    """Newline-delimited JSON events (see converse). {"type": "ai_off"} alone: use POST /api/ask instead."""
    currency = currency_seen(db, user)
    organization_id = user.organization_id
    earlier = None
    if body.previous:
        earlier = checked_question({"type": body.previous.type, **body.previous.filters}, shop_words(db, organization_id))
        if earlier is None or earlier.type == "cannot_answer":
            raise HTTPException(422, "That isn't a filter this question type takes.")

    language, cloud = app_language(db, user), cloud_on(db, user)

    def events():
        if not llm.is_on():
            yield as_line({"type": "ai_off"})
            return
        with SessionLocal() as own_db:  # its own session: the answer is still being written after this function returns
            for event in converse(own_db, organization_id, currency, body.question, earlier, language, cloud):
                if event["type"] == "done":
                    remember(own_db, user, body.question, "assistant", json.loads(as_line(event)))
                yield as_line(event)

    return StreamingResponse(events(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache"})


@router.post("")
def ask(body: AskIn, user: User = Depends(anyone), db: Session = Depends(get_session)) -> AskOut:
    currency = currency_seen(db, user)
    if body.filters is not None:
        # A filter chip was changed: keep the question type, replace its filters, nothing re-read.
        if not body.question_type:
            raise HTTPException(422, "A filter needs the question type it belongs to.")
        question = checked_question({"type": body.question_type, **body.filters}, shop_words(db, user.organization_id))
        if question is None:
            raise HTTPException(422, "That isn't a filter this question type takes.")
        understood_by, ai_on = "rule", llm.is_on()
    elif body.question_type:
        understood = understand_as(db, user.organization_id, body.question, body.question_type)
        question, understood_by, ai_on = understood.question, understood.understood_by, understood.ai_on
    else:
        understood = understand(db, user.organization_id, body.question)
        question, understood_by, ai_on = understood.question, understood.understood_by, understood.ai_on
    result = answer(db, user.organization_id, question, currency)
    line = understood_line(question)
    if line and understood_by == "model":
        line = BEST_GUESS + line
    language = reply_language(body.question, app_language(db, user))
    out = AskOut(
        understood=line,
        question_type=question.type,
        filters=question.filters(),
        understood_by=understood_by,
        ai_note=None if ai_on else AI_OFF,
        ai_on=ai_on,
        period=shown_period(question) if question.type in QUESTION_TYPES else None,
        key=result.key,
        values=result.values,
        answer=written_answer(result, language, currency),
        language=language,
        numbers=result.numbers,
        suggestions=[_suggestion(question, question_type) for question_type in question.suggestions],
    )
    remember(db, user, body.question, "rule", out.model_dump(mode="json"))
    return out


def _suggestion(question: Question, question_type: str) -> Suggestion:
    """Labeled with what was understood so far: "Stock · Rabat - Agdal"."""
    used = QUESTION_TYPES[question_type]
    kept = {name: value for name, value in question.filters().items() if name in used and name != "part"}
    suggested = Question(question_type, **kept)
    return Suggestion(question_type=question_type, label=heading(suggested), filters=kept, period=shown_period(suggested))
