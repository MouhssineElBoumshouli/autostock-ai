"""Pieces every answer uses: the answer shape, who is asking, and which parts and branch they mean."""

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import ColumnElement, func, select, true
from sqlalchemy.orm import Session

from app.alerts.problem import day_label, money
from app.ask.question import Question
from app.models import Branch, Part, SaleLine
from app.search.part_search import find_parts

Unit = Literal["pieces", "money", "count", "days", "date", "percent", "text"]
SHOWN_ROWS = 5


class Number(BaseModel):
    """One real number the answer used. Money is in centimes."""

    label: str
    value: int | float | str
    unit: Unit


@dataclass
class Answer:
    sentence: str
    numbers: list[Number] = field(default_factory=list)


@dataclass
class Asked:
    """Who asks, about which shop, and what "today" is for this shop."""

    db: Session
    organization_id: uuid.UUID
    question: Question
    today: date
    currency: str | None  # None = this person doesn't see money

    def money_words(self, centimes: int, before: str = ", worth ") -> str:
        return f"{before}{money(centimes, self.currency)}" if self.currency else ""

    def money_number(self, label: str, centimes: int) -> list[Number]:
        return [Number(label=label, value=centimes, unit="money")] if self.currency else []


@dataclass
class PartPick:
    condition: ColumnElement  # on Part
    label: str  # "Oil filter (12 parts)", "the Brakes category", "all parts"


def shop_today(db: Session, organization_id: uuid.UUID) -> date:
    """The last day with sales, or the calendar day if the shop has no sales yet."""
    last_sale = db.scalar(select(func.max(SaleLine.sold_on)).where(SaleLine.organization_id == organization_id))
    return last_sale or date.today()


def pick_parts(asked: Asked) -> PartPick | None:
    """The parts the question is about. None when it names a part the shop doesn't have."""
    question = asked.question
    if question.part:
        result = find_parts(asked.db, asked.organization_id, question.part)
        if result.closest or not result.matches:
            return None
        ids = [part_id for part_id, _ in result.matches]
        names = sorted(set(asked.db.scalars(select(Part.name).where(Part.id.in_(ids)))))
        label = names[0] if len(names) == 1 else f"parts matching “{question.part}”"
        return PartPick(Part.id.in_(ids), label if len(ids) == 1 else f"{label} ({len(ids)} parts)")
    if question.category:
        return PartPick(Part.category == question.category, f"the {question.category} category")
    return PartPick(true(), "all parts")


def branch_id(asked: Asked) -> uuid.UUID | None:
    if not asked.question.branch:
        return None
    return asked.db.scalar(
        select(Branch.id).where(Branch.organization_id == asked.organization_id, Branch.name == asked.question.branch)
    )


def where_words(asked: Asked) -> str:
    return f" in {asked.question.branch}" if asked.question.branch else ""


def range_words(first: date, last: date) -> str:
    return day_label(first) if first == last else f"{day_label(first)} – {day_label(last)}"


def part_not_found(asked: Asked) -> Answer:
    return Answer(f"I couldn't find a part matching “{asked.question.part}”. Try its name or part number.")


def which_part(example: str) -> Answer:
    return Answer(f"Which part? For example: “{example}”.")
