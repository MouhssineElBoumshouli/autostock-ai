"""Shared pieces for planning an import: problems, the summary, and branch/supplier names."""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.imports.fields import FIELDS, ImportKind
from app.imports.reading import Table
from app.models import Branch, Supplier


@dataclass
class Problem:
    row: int
    messages: list[str]


@dataclass
class Summary:
    """What the Check step shows and the Save step writes."""

    counts: dict[str, int]
    new_suppliers: list[str] = field(default_factory=list)
    new_branches: list[str] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)


def cells_by_field(table: Table, columns: dict[str, int]):
    """Yields (row number, {field: raw cell}) for every data row."""
    for number, cells in table.rows:
        yield number, {key: cells[index] for key, index in columns.items()}


def find_duplicates(keys_by_row: dict[int, str]) -> dict[int, list[int]]:
    """{row: [all rows with the same key]} for keys that appear more than once."""
    rows_by_key: dict[str, list[int]] = defaultdict(list)
    for row, key in keys_by_row.items():
        rows_by_key[key].append(row)
    return {row: rows for rows in rows_by_key.values() if len(rows) > 1 for row in rows}


def label(kind: ImportKind, key: str) -> str:
    return next(f.label for f in FIELDS[kind] if f.key == key)


class NameBook:
    """Branches or suppliers of one shop, found by name ignoring case; unknown names become new ones."""

    def __init__(self, db: Session, model: type[Branch] | type[Supplier], organization_id: uuid.UUID):
        self.model = model
        self.organization_id = organization_id
        rows = db.scalars(select(model).where(model.organization_id == organization_id)).all()
        self.by_name: dict[str, Any] = {row.name.lower(): row for row in rows}
        self.new_names: dict[str, str] = {}  # lowercase -> name as first written

    def note(self, name: str) -> None:
        if name.lower() not in self.by_name:
            self.new_names.setdefault(name.lower(), name)

    def existing_id(self, name: str) -> uuid.UUID | None:
        row = self.by_name.get(name.lower())
        return row.id if row else None

    def create_new(self, db: Session) -> None:
        for lower, name in self.new_names.items():
            row = self.model(organization_id=self.organization_id, name=name)
            db.add(row)
            self.by_name[lower] = row
        db.flush()

    def id_of(self, name: str) -> uuid.UUID:
        return self.by_name[name.lower()].id


def main_branch(db: Session, organization_id: uuid.UUID) -> Branch:
    """The shop's first branch: used when a file has no branch column."""
    return db.scalars(
        select(Branch).where(Branch.organization_id == organization_id).order_by(Branch.created_at)
    ).first()
