"""Turning a typed question into a checked Question.

Measured 2026-10-20 (right / wrong question answered): first set rule 86% / 0%, hybrid with
qwen2.5:3b 97% / 2%; counter set rule 70% / 0%, hybrid 90% / 7%. Hybrid is used: every answer
shows "I understood: ..." so a wrong reading is visible, and with AI off it is the rule alone.

READER says how, chosen by measuring every way on both labeled question sets
(app/ask/check_questions.py, results in docs/journey.md):
- "rule": the keyword rule only; when it is unsure it asks the person.
- "hybrid": the rule first; the local model only when the rule is unsure, and the model may only
  pick one of the question types the rule would have offered as buttons. If the model is off, its
  answer isn't allowed, or it picks another type, the person is asked, as with the rule alone.
"""

import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import llm
from app.ask.keyword_rule import read_with_rule
from app.ask.model_reader import read_with_model
from app.ask.question import FILTERS, NOT_SURE, QUESTION_TYPES, Question, ShopWords, checked_question
from app.ask.words import vocabulary
from app.models import Branch, Part, SynonymGroup

READER: Literal["rule", "hybrid"] = "hybrid"


@dataclass(frozen=True)
class Understood:
    question: Question
    understood_by: Literal["model", "rule"]
    ai_on: bool


def shop_words(db: Session, organization_id: uuid.UUID) -> ShopWords:
    in_shop = Part.organization_id == organization_id
    categories = db.scalars(select(Part.category).where(in_shop, Part.category.is_not(None)).distinct())
    branches = db.scalars(select(Branch.name).where(Branch.organization_id == organization_id))
    names = db.scalars(select(func.concat_ws(" ", Part.name, Part.brand)).where(in_shop))
    synonyms = db.scalars(select(func.unnest(SynonymGroup.words)).where(SynonymGroup.organization_id == organization_id))
    return ShopWords(tuple(sorted(categories)), tuple(sorted(branches)), vocabulary([*names, *synonyms]))


def understand(db: Session, organization_id: uuid.UUID, text: str) -> Understood:
    shop = shop_words(db, organization_id)
    ai_on = llm.is_on()
    by_rule = read_with_rule(text, shop)
    if READER == "rule" or by_rule.type != NOT_SURE or not ai_on:
        return Understood(by_rule, "rule", ai_on)
    by_model = read_with_model(text, shop)
    if not model_reading_usable(by_rule, by_model):
        return Understood(by_rule, "rule", ai_on)
    return Understood(by_model, "model", ai_on)


def model_reading_usable(by_rule: Question, by_model: Question | None) -> bool:
    """The model fills in for an unsure rule only with one of the rule's own suggestions."""
    return by_model is not None and by_model.type in by_rule.suggestions


def understand_as(db: Session, organization_id: uuid.UUID, text: str, question_type: str) -> Understood:
    """The person picked the question type (a "Did you mean" button): keep what the rule understood
    of the filters, under that type. Words the rule didn't know are then searched as the part."""
    shop = shop_words(db, organization_id)
    by_rule = read_with_rule(text, shop)
    used = QUESTION_TYPES[question_type]
    raw = {name: getattr(by_rule, name) for name in FILTERS if name in used}
    question = checked_question({"type": question_type, **raw}, shop) or Question(question_type)
    return Understood(question, "rule", llm.is_on())
