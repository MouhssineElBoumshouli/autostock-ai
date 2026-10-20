"""Turning a typed question into a checked Question.

The keyword rule is the baseline. The local model is used only while it reads the labeled questions
better than the rule (app/ask/check_questions.py). Measured 2026-10-20 on 90 questions: rule 93%,
qwen2.5:1.5b 44% — so the rule is used, and the model stays ready for a model that beats it.
"""

import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import llm
from app.ask.keyword_rule import read_with_rule
from app.ask.model_reader import read_with_model
from app.ask.question import Question, ShopWords
from app.models import Branch, Part

MODEL_BEATS_RULE = False


@dataclass(frozen=True)
class Understood:
    question: Question
    understood_by: Literal["model", "rule"]
    ai_on: bool


def shop_words(db: Session, organization_id: uuid.UUID) -> ShopWords:
    categories = db.scalars(
        select(Part.category).where(Part.organization_id == organization_id, Part.category.is_not(None)).distinct()
    )
    branches = db.scalars(select(Branch.name).where(Branch.organization_id == organization_id))
    return ShopWords(tuple(sorted(categories)), tuple(sorted(branches)))


def understand(db: Session, organization_id: uuid.UUID, text: str) -> Understood:
    shop = shop_words(db, organization_id)
    if not llm.is_on():
        return Understood(read_with_rule(text, shop), "rule", ai_on=False)
    if not MODEL_BEATS_RULE:
        return Understood(read_with_rule(text, shop), "rule", ai_on=True)
    question = read_with_model(text, shop)
    if question is None:
        return Understood(read_with_rule(text, shop), "rule", ai_on=True)
    return Understood(question, "model", ai_on=True)
