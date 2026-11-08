"""What every data tool shares: who is asking (their shop, whether they see money), the shop's dates,
and turning the assistant's arguments (part type, car, brand, branch, dates) into checked filters.

A part is found field by field, and a part must match EVERY field given: "type: filtre à huile, car:
Dacia Logan" is the Logan's oil filter, never every Logan part. Part names are "Type - Car" in most
shops ("Filtre à huile - Dacia Logan"). The type and the car are first matched to the shop's own type and
car names, word by word ("disques frein avant" is "Disques de frein avant (paire)", not the pads); when no
name has all the words, they are searched like the stock search does (typos, synonyms, other languages),
keeping only the parts matching all their words.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import ColumnElement, func, select, true
from sqlalchemy.orm import Session

from app.ask.answer_parts import Number
from app.models import Branch, Part
from app.search.part_search import content_words, find_parts

TEXT = {"type": "string"}
PART = {"type": TEXT, "car": TEXT, "brand": TEXT}  # the part fields every tool takes
DATES = {"date_from": TEXT, "date_to": TEXT}
TOP = {"top": {"type": "integer"}}
ROWS = 10  # rows a tool gives by default; the assistant may ask for up to MAX_ROWS
MAX_ROWS = 20
PART_FIELDS = ("type", "car", "brand", "oem", "category")
TYPE_NAME = func.split_part(Part.name, " - ", 1)  # "Filtre à huile" in "Filtre à huile - Dacia Logan"
CAR_NAME = func.split_part(Part.name, " - ", 2)  # "Dacia Logan"


class ToolError(Exception):
    """A wrong or unknown argument: the assistant is told exactly what, and may try again."""

    def __init__(self, message: str, **details):
        super().__init__(message)
        self.details = {"error": message, **details}


@dataclass
class Asker:
    db: Session
    organization_id: uuid.UUID
    today: date  # the shop's calendar day
    last_sale_day: date | None  # the newest sale imported
    currency: str | None  # None: this person doesn't see money

    @property
    def sees_money(self) -> bool:
        return self.currency is not None

    def money(self, centimes: int | float | None) -> float | None:
        """Money for the assistant, in the shop's currency (MAD), or None for people who don't see it."""
        if not self.sees_money or centimes is None:
            return None
        return round(centimes / 100, 2)


@dataclass
class ToolResult:
    data: dict  # what the assistant reads (compact JSON)
    shown: list[Number] = field(default_factory=list)  # the numbers shown under "Based on"
    heading: dict = field(default_factory=dict)  # the filters used, shown above those numbers


@dataclass
class PartChoice:
    condition: ColumnElement  # on Part
    asked: dict  # the fields given, for the "Based on" heading
    matched: int  # how many parts
    types: list[str]  # their types (names before " - "), at most a few

    def described(self) -> dict:
        """For the assistant: how many part references were counted, and their types (only when a part was asked)."""
        return {"part_references": self.matched, "types": self.types} if self.asked else {}


def rows_wanted(args: dict) -> int:
    top = args.get("top")
    return max(1, min(int(top), MAX_ROWS)) if isinstance(top, int) or str(top).isdigit() else ROWS


def part_choice(asker: Asker, args: dict) -> PartChoice:
    """The parts the arguments mean; raises ToolError when a field matches no part (with the closest names)."""
    asked = {name: str(args[name]).strip() for name in PART_FIELDS if str(args.get(name) or "").strip()}
    in_shop = Part.organization_id == asker.organization_id
    if not asked:
        return PartChoice(true(), {}, asker.db.scalar(select(func.count()).where(in_shop)) or 0, [])
    ids: set[uuid.UUID] | None = None
    for name, column in (("type", TYPE_NAME), ("car", CAR_NAME)):
        if name in asked:
            ids = _intersect(ids, _named(asker, column, asked[name]) or _searched(asker, name, asked[name]))
    conditions = [in_shop]
    if ids is not None:
        conditions.append(Part.id.in_(ids))
    if "brand" in asked:
        conditions.append(func.lower(Part.brand) == asked["brand"].lower())
    if "category" in asked:
        conditions.append(func.lower(Part.category) == asked["category"].lower())
    if "oem" in asked:
        code = asker.db.scalar(select(func.search_code(asked["oem"])))
        conditions.append(Part.oem_key.contains(code) | Part.sku_key.contains(code))
    found = asker.db.execute(select(Part.id, TYPE_NAME).where(*conditions)).all()
    if not found:
        raise ToolError("No part matches all of these.", asked=asked, hint="Try fewer fields, or find_parts.")
    types = sorted({type_name for _, type_name in found})
    return PartChoice(Part.id.in_([part_id for part_id, _ in found]), asked, len(found), types[:8])


def _named(asker: Asker, column, words: str) -> set[uuid.UUID]:
    """Parts whose type (or car) name has every typed word, or a word starting with it ("plaquette" in
    "plaquettes"). Empty when no name does."""
    typed = content_words(asker.db.scalar(select(func.search_text(words))).split())
    names = asker.db.execute(select(column, func.search_text(column)).where(Part.organization_id == asker.organization_id)
                             .distinct()).all()
    wanted = [name for name, cleaned in names if typed and all(_has_word(cleaned.split(), word) for word in typed)]
    if not wanted:
        return set()
    return set(asker.db.scalars(select(Part.id).where(Part.organization_id == asker.organization_id, column.in_(wanted))))


def _has_word(words: list[str], typed: str) -> bool:
    return any(word.startswith(typed) or word.rstrip("sx") == typed.rstrip("sx") for word in words)


def _searched(asker: Asker, name: str, words: str) -> set[uuid.UUID]:
    result = find_parts(asker.db, asker.organization_id, words, every_word=True)
    if result.closest or not result.matches:
        closest = asker.db.scalars(select(Part.name).where(Part.id.in_([i for i, _ in result.matches[:5]]))).all()
        raise ToolError(f"No part has the {name} '{words}'.", closest=sorted(set(closest)))
    return {part_id for part_id, _ in result.matches}


def _intersect(ids: set[uuid.UUID] | None, more: set[uuid.UUID]) -> set[uuid.UUID]:
    return more if ids is None else ids & more


def branch_choice(asker: Asker, args: dict) -> tuple[uuid.UUID | None, str | None]:
    """The branch named ("Rabat" finds "Rabat - Agdal"), or (None, None) for all branches."""
    wanted = str(args.get("branch") or "").strip()
    if not wanted:
        return None, None
    branches = asker.db.execute(select(Branch.id, Branch.name).where(Branch.organization_id == asker.organization_id)).all()
    for branch_id, name in branches:
        if wanted.lower() == name.lower():
            return branch_id, name
    near = [(branch_id, name) for branch_id, name in branches if wanted.lower() in name.lower()]
    if len(near) == 1:
        return near[0]
    raise ToolError(f"Unknown branch '{wanted}'.", branches=[name for _, name in branches])


def period_choice(asker: Asker, args: dict, default_days: int = 30) -> tuple[date, date]:
    """date_from and date_to (included). Without them: the `default_days` days up to the newest sale imported
    (or today when there is none), so "why did sales drop?" isn't answered with days not imported yet."""
    try:
        last = date.fromisoformat(args["date_to"]) if args.get("date_to") else (asker.last_sale_day or asker.today)
        first = date.fromisoformat(args["date_from"]) if args.get("date_from") else last - timedelta(days=default_days - 1)
    except (TypeError, ValueError) as error:
        raise ToolError("Dates must be written YYYY-MM-DD.") from error
    if first > last:
        raise ToolError("date_from is after date_to.")
    return first, last


def asked_heading(choice: PartChoice, branch: str | None, first: date | None = None, last: date | None = None) -> dict:
    """The filters as the website shows them above a lookup's numbers."""
    heading = {name: value for name, value in choice.asked.items()}
    if branch:
        heading["branch"] = branch
    if first and last:
        heading["range"] = f"{first.isoformat()}/{last.isoformat()}"
    return heading


def percent_change(now: int | float, before: int | float) -> int | None:
    """Rounded % change, computed by the app so the assistant never does arithmetic. None when before is 0."""
    return round((now - before) * 100 / before) if before else None
