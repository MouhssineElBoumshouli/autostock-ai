"""Parts that are the same part under another brand: same OEM number (automatic, from
parts.oem_key), a manager's link, or a row from a supplier's cross-reference file. If A and B are
the same, and B and C are the same, then A and C are the same: equivalents form groups, not pairs.

Every lookup here expands outward from a known handful of parts (the ones on screen), one
database query per hop. None of it ever loads a whole shop's parts or links, so a search stays
fast no matter how big the catalog is - only the size of an equivalence group matters, and those
stay small (a few brands of the same part).
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, aliased

from app.models import Part, PartEquivalent


@dataclass
class Reached:
    part_id: uuid.UUID
    link_id: uuid.UUID | None  # None for an automatic same-OEM-number match: there is nothing to remove
    reason_type: str  # "oem" | "manual" | "supplier_file"
    linked_by: uuid.UUID | None  # the manager who made a "manual" link


@dataclass
class Edge:
    node: uuid.UUID  # the part already in the frontier
    other: uuid.UUID  # the part it leads to
    reason_type: str
    link_id: uuid.UUID | None
    linked_by: uuid.UUID | None


def _expand(db: Session, organization_id: uuid.UUID, frontier: set[uuid.UUID]) -> list[Edge]:
    """Every same-OEM-number match or stored link touching a part in `frontier`. One query for
    each (a self-join, not "load this part's code, then look up who shares it" as two queries)."""
    edges: list[Edge] = []

    origin, other = aliased(Part), aliased(Part)
    same_oem = db.execute(
        select(origin.id, other.id).join(
            other,
            (other.organization_id == origin.organization_id) & (other.oem_key == origin.oem_key) & (other.id != origin.id),
        ).where(origin.id.in_(frontier), origin.organization_id == organization_id, origin.oem_key != "")
    ).all()
    edges += [Edge(node, other_id, "oem", None, None) for node, other_id in same_oem]

    links = db.scalars(
        select(PartEquivalent).where(
            PartEquivalent.organization_id == organization_id,
            or_(PartEquivalent.part_a_id.in_(frontier), PartEquivalent.part_b_id.in_(frontier)),
        )
    ).all()
    for link in links:
        if link.part_a_id in frontier:
            edges.append(Edge(link.part_a_id, link.part_b_id, link.source, link.id, link.created_by_user_id))
        if link.part_b_id in frontier:
            edges.append(Edge(link.part_b_id, link.part_a_id, link.source, link.id, link.created_by_user_id))
    return edges


def reachable_from(db: Session, organization_id: uuid.UUID, part_id: uuid.UUID) -> list[Reached]:
    """Every part in the same equivalence group as part_id, however many links away, with how it
    was first reached. A part reached only through others (A-B-C) still counts: if A=B and B=C,
    then A=C."""
    visited: dict[uuid.UUID, Reached] = {}
    frontier = {part_id}
    while frontier:
        next_frontier: set[uuid.UUID] = set()
        for edge in _expand(db, organization_id, frontier):
            if edge.other != part_id and edge.other not in visited:
                visited[edge.other] = Reached(
                    part_id=edge.other, link_id=edge.link_id, reason_type=edge.reason_type, linked_by=edge.linked_by
                )
                next_frontier.add(edge.other)
        frontier = next_frontier
    return list(visited.values())


def groups_of(db: Session, organization_id: uuid.UUID, part_ids: list[uuid.UUID]) -> dict[uuid.UUID, set[uuid.UUID]]:
    """For each of these parts, every part id in the same equivalence group (itself included).
    One combined, union-find expansion from all of them at once."""
    if not part_ids:
        return {}
    parent: dict[uuid.UUID, uuid.UUID] = {}

    def find(node: uuid.UUID) -> uuid.UUID:
        parent.setdefault(node, node)
        while parent[node] != node:
            node = parent[node]
        return node

    def union(a: uuid.UUID, b: uuid.UUID) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_a] = root_b

    seen = set(part_ids)
    frontier = set(part_ids)
    while frontier:
        next_frontier: set[uuid.UUID] = set()
        for edge in _expand(db, organization_id, frontier):
            union(edge.node, edge.other)
            if edge.other not in seen:
                seen.add(edge.other)
                next_frontier.add(edge.other)
        frontier = next_frontier

    members: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for node in seen:
        members[find(node)].add(node)
    return {part_id: members[find(part_id)] for part_id in part_ids}
