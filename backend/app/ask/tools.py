"""Running a question the app understood: its read-only answer, scoped to the asker's shop, with no
money for people who don't see it. Comparisons and percentages are computed here, by the app.
"""

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
