"""Running a question the app understood: its read-only answer (scoped to the asker's shop, no
money for people who don't see it), and the facts the model writes the answer from.

Comparisons and percentages are already in the facts (computed by the app), so the model never
has to calculate anything.
"""

import json
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ask.answer_parts import Answer
from app.ask.answers import answer
from app.ask.question import Question


@dataclass
class Lookup:
    question: Question
    answer: Answer

    @property
    def tool(self) -> str:
        return self.question.type

    @property
    def filters(self) -> dict[str, str]:
        return self.question.filters()


def look_up(db: Session, organization_id: uuid.UUID, currency: str | None, question: Question) -> Lookup:
    return Lookup(question, answer(db, organization_id, question, currency))


def for_the_model(lookup: Lookup, currency: str | None) -> str:
    """What the model reads: the app's own sentence, the facts and the numbers. Money is in the
    shop's currency (not centimes), so the model never has to convert it."""
    numbers = [
        {"label": number.label, "value": _money(number.value) if number.unit == "money" else number.value}
        for number in lookup.answer.numbers
    ]
    content = {"question": lookup.tool, "filters_used": lookup.filters, "summary": lookup.answer.sentence,
               "facts": _with_money(lookup.answer.values), "numbers": numbers}
    if currency:
        content["currency"] = currency
    return json.dumps(content, ensure_ascii=False, default=str)


def _money(centimes: object) -> object:
    return centimes / 100 if isinstance(centimes, int) else centimes


def _with_money(value: object, key: str = "") -> object:
    if isinstance(value, dict):
        return {k: _with_money(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_with_money(v) for v in value]
    return _money(value) if key == "money" or key.endswith("_money") else value
