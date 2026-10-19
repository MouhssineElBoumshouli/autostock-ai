"""Parts that are the same part under another brand: same OEM number (automatic, from
parts.oem_key), a manager's link, or a row from a supplier's cross-reference file. If A and B are
the same, and B and C are the same, then A and C are the same: equivalents form groups, not pairs.
"""

import uuid
from collections import defaultdict, deque
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Part, PartEquivalent


@dataclass
class Reached:
    part_id: uuid.UUID
    link_id: uuid.UUID | None  # None for an automatic same-OEM-number match: there is nothing to remove
    reason_type: str  # "oem" | "manual" | "supplier_file"
    linked_by: uuid.UUID | None  # the manager who made a "manual" link


@dataclass
class EquivalentGraph:
    organization_id: uuid.UUID
    oem_of: dict[uuid.UUID, str]  # part_id -> oem_key, only for parts that have one
    by_oem: dict[str, list[uuid.UUID]]
    links: dict[uuid.UUID, list[tuple[uuid.UUID, PartEquivalent]]]  # part_id -> [(other part, link)]


def load_graph(db: Session, organization_id: uuid.UUID) -> EquivalentGraph:
    oem_of: dict[uuid.UUID, str] = {}
    by_oem: dict[str, list[uuid.UUID]] = defaultdict(list)
    for part_id, oem_key in db.execute(select(Part.id, Part.oem_key).where(Part.organization_id == organization_id)):
        if oem_key:
            oem_of[part_id] = oem_key
            by_oem[oem_key].append(part_id)

    links: dict[uuid.UUID, list[tuple[uuid.UUID, PartEquivalent]]] = defaultdict(list)
    for link in db.scalars(select(PartEquivalent).where(PartEquivalent.organization_id == organization_id)):
        links[link.part_a_id].append((link.part_b_id, link))
        links[link.part_b_id].append((link.part_a_id, link))
    return EquivalentGraph(organization_id=organization_id, oem_of=oem_of, by_oem=by_oem, links=links)


def reachable_from(graph: EquivalentGraph, part_id: uuid.UUID) -> list[Reached]:
    """Every part in the same equivalence group, however many links away, with how it was first
    reached. A part reached only through others (A-B-C) still counts: if A=B and B=C, then A=C."""
    visited: dict[uuid.UUID, Reached] = {}
    queue = deque([part_id])
    while queue:
        current = queue.popleft()
        neighbors: list[Reached] = []
        oem = graph.oem_of.get(current)
        if oem:
            neighbors += [
                Reached(part_id=other, link_id=None, reason_type="oem", linked_by=None)
                for other in graph.by_oem[oem] if other != current
            ]
        neighbors += [
            Reached(part_id=other, link_id=link.id, reason_type=link.source, linked_by=link.created_by_user_id)
            for other, link in graph.links[current]
        ]
        for reached in neighbors:
            if reached.part_id != part_id and reached.part_id not in visited:
                visited[reached.part_id] = reached
                queue.append(reached.part_id)
    return list(visited.values())


def has_group(graph: EquivalentGraph, part_id: uuid.UUID) -> bool:
    oem = graph.oem_of.get(part_id)
    return bool(oem and len(graph.by_oem[oem]) > 1) or bool(graph.links[part_id])
