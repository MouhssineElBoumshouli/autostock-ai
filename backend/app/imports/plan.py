"""Shared pieces for planning an import: problems, the summary, and branch/supplier names."""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.imports.fields import FIELDS, ImportKind
from app.imports.reading import Table
from app.models import Branch, Supplier

ROWS_PER_SEND = 10_000  # rows written to PostgreSQL at a time
PROBLEMS_KEPT = 200  # the report shows these, plus how many there are in all


@dataclass
class Problem:
    row: int
    messages: list[str]
    sheet: str | None = None


class ProblemReport:
    """Every row with a problem is counted, but only the first ones are kept: a wrong file can have
    a problem on each of its 2 million rows."""

    def __init__(self) -> None:
        self.count = 0
        self.first: list[Problem] = []

    def add(self, row: int, messages: list[str], sheet: str | None = None) -> None:
        self.count += 1
        if len(self.first) < PROBLEMS_KEPT:
            self.first.append(Problem(row, messages, sheet))


@dataclass
class Summary:
    """What the Check step shows and the Save step writes."""

    counts: dict[str, int]
    new_suppliers: list[str] = field(default_factory=list)
    new_branches: list[str] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)
    problem_count: int = 0


def cells_by_field(table: Table, columns: dict[str, int]) -> Iterator[tuple[int, dict[str, Any]]]:
    """Yields (row number, {field: raw cell}) for every data row."""
    pairs = list(columns.items())
    for number, cells in table.read():
        yield number, {key: cells[index] for key, index in pairs}


def copy_cell(value: Any) -> str:
    """One value for PostgreSQL's COPY text format."""
    if value is None:
        return r"\N"
    return str(value).replace("\\", "\\\\").replace("\t", " ").replace("\n", " ").replace("\r", " ")


def send_rows(db: Session, table_name: str, lines: list[str]) -> None:
    """Adds finished COPY lines to a table, in this transaction."""
    cursor = db.connection().connection.dbapi_connection.cursor()
    with cursor.copy(f"COPY {table_name} FROM STDIN") as copy:
        copy.write("".join(lines).encode())


def give_room_to_sort(db: Session) -> None:
    """Room for PostgreSQL to compare a whole file's lines in memory, for this transaction."""
    db.execute(text("SET LOCAL work_mem = '128MB'"))


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

    def create_new(self, db: Session) -> None:
        for lower, name in self.new_names.items():
            row = self.model(organization_id=self.organization_id, name=name)
            db.add(row)
            self.by_name[lower] = row
        db.flush()


def main_branch(db: Session, organization_id: uuid.UUID) -> Branch:
    """The shop's first branch: used when a file has no branch column."""
    return db.scalars(
        select(Branch).where(Branch.organization_id == organization_id).order_by(Branch.created_at)
    ).first()
