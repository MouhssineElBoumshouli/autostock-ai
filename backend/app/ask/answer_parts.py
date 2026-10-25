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

Unit = Literal["pieces", "money", "count", "days", "date", "date_range", "percent", "text", "alert_kind"]
SHOWN_ROWS = 5
SHOWN_PARTS = 10  # a part word matching several parts: how many get their own line, besides the total


class Number(BaseModel):
    """One real number the answer used. Money is in centimes, a date is "2026-10-21", a date
    range is "2026-10-01/2026-10-21". `key` names a fixed label ("pieces_sold") that the website
    shows in the person's language, with `about` (a part, an order) when the label is about one.
    Without a key, `label` is the shop's own words (a part, a branch) and is shown as it is."""

    label: str
    value: int | float | str
    unit: Unit
    key: str | None = None
    about: str | None = None


@dataclass
class Answer:
    """`sentence` is English. The website builds the same sentence in the person's language from
    `key` and `values` (the real numbers and names it says), see frontend/src/i18n."""

    key: str
    values: dict
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

    def money_number(self, key: str, label: str, centimes: int) -> list[Number]:
        return [Number(key=key, label=label, value=centimes, unit="money")] if self.currency else []

    def money_value(self, centimes: int) -> dict:
        """{"money": centimes} for people who see money, else nothing."""
        return {"money": centimes} if self.currency else {}

    def place(self) -> dict:
        """{"branch": name} when the question is about one branch."""
        return {"branch": self.question.branch} if self.question.branch else {}


@dataclass
class PartPick:
    condition: ColumnElement  # on Part
    label: str  # "Oil filter (12 parts)", "the Brakes category", "all parts"
    subject: dict  # the same for the website: {"kind": "part" | "matching" | "category" | "all", ...}
    part_ids: tuple[uuid.UUID, ...] = ()  # set only when a part word matched more than one part

    @property
    def title(self) -> str:
        """The label at the start of a sentence: only the first letter changes."""
        return self.label[:1].upper() + self.label[1:]


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
        subject = {"kind": "part", "name": names[0]} if len(names) == 1 else {"kind": "matching", "words": question.part}
        if len(ids) > 1:
            subject["count"] = len(ids)
        return PartPick(
            Part.id.in_(ids), label if len(ids) == 1 else f"{label} ({len(ids)} parts)", subject,
            part_ids=tuple(ids) if len(ids) > 1 else (),
        )
    if question.category:
        return PartPick(
            Part.category == question.category, f"the {question.category} category",
            {"kind": "category", "name": question.category},
        )
    return PartPick(true(), "all parts", {"kind": "all"})


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


def date_range(first: date, last: date) -> str:
    return f"{first.isoformat()}/{last.isoformat()}"


def part_not_found(asked: Asked) -> Answer:
    return Answer(
        "part_not_found", {"part": asked.question.part},
        f"I couldn't find a part matching “{asked.question.part}”. Try its name or part number.",
    )


def which_part(key: str, example: str) -> Answer:
    """`key` is which_part_stock or which_part_forecast: each shows its own example question."""
    return Answer(key, {}, f"Which part? For example: “{example}”.")
