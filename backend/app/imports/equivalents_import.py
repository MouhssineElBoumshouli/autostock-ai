"""Import of "Equivalent parts" files: a supplier's cross-reference file, two codes per row. Each
code is matched the same way part search matches part numbers: spaces, dashes and dots removed
(see search_code, migration 0006). Both codes must already be one of our parts, by SKU or OEM
reference - this file links parts we carry, it does not create new ones.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.imports.plan import Problem, Summary, cells_by_field
from app.imports.reading import Table
from app.imports.values import clean_text
from app.models import Part, PartEquivalent


@dataclass
class EquivalentsPlan:
    summary: Summary
    pairs: list[tuple[uuid.UUID, uuid.UUID]]  # part_a_id < part_b_id, not already linked


def plan_equivalents(db: Session, organization_id: uuid.UUID, table: Table, columns: dict[str, int]) -> EquivalentsPlan:
    by_code: dict[str, list[uuid.UUID]] = {}
    for part_id, sku_key, oem_key in db.execute(
        select(Part.id, Part.sku_key, Part.oem_key).where(Part.organization_id == organization_id)
    ):
        for key in (sku_key, oem_key):
            if key:
                by_code.setdefault(key, []).append(part_id)

    existing = {
        _ordered(link.part_a_id, link.part_b_id)
        for link in db.scalars(select(PartEquivalent).where(PartEquivalent.organization_id == organization_id))
    }

    codes_seen: dict[str, str] = {}
    pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()
    problems: list[Problem] = []
    for number, cells in cells_by_field(table, columns):
        messages: list[str] = []
        our_part = _one_match(db, by_code, codes_seen, cells.get("our_code"), "Our code", messages)
        other_part = _one_match(db, by_code, codes_seen, cells.get("equivalent_code"), "Equivalent code", messages)
        if our_part and other_part and our_part == other_part:
            messages.append("Our code and the equivalent code are the same part")
        if messages:
            problems.append(Problem(row=number, messages=messages))
        elif our_part and other_part:
            pairs.add(_ordered(our_part, other_part))

    new_pairs = pairs - existing
    summary = Summary(
        counts={
            "new_equivalents": len(new_pairs),
            "already_linked": len(pairs) - len(new_pairs),
            "problem_rows": len(problems),
        },
        problems=problems,
    )
    return EquivalentsPlan(summary=summary, pairs=sorted(new_pairs))


def save_equivalents(db: Session, organization_id: uuid.UUID, user_id: uuid.UUID, plan: EquivalentsPlan) -> None:
    db.add_all(
        PartEquivalent(
            organization_id=organization_id, part_a_id=a, part_b_id=b, source="supplier_file", created_by_user_id=user_id,
        )
        for a, b in plan.pairs
    )


def _ordered(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (a, b) if a < b else (b, a)


def _one_match(
    db: Session, by_code: dict[str, list[uuid.UUID]], codes_seen: dict[str, str], raw, label: str, messages: list[str]
) -> uuid.UUID | None:
    text = clean_text(raw)
    if not text:
        messages.append(f"{label} is missing")
        return None
    if text not in codes_seen:
        codes_seen[text] = db.scalar(select(func.search_code(text)))
    matches = by_code.get(codes_seen[text], [])
    if not matches:
        messages.append(f"{label} “{text}” is not one of your parts")
        return None
    if len(matches) > 1:
        messages.append(f"{label} “{text}” matches more than one of your parts")
        return None
    return matches[0]
