"""Branches: the owner can rename, merge (moving its stock and sales into another branch) or
remove one that was created by mistake and never used.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.api.schemas import NameText
from app.audit import record_change
from app.auth.permissions import require_role
from app.db import get_session
from app.models import Branch, Forecast, SaleLine, StockLevel, StockOut, User

router = APIRouter(prefix="/api/branches")
owner_only = require_role("owner")

NEEDS_ONE_BRANCH = "The shop needs at least one branch."


class BranchOut(BaseModel):
    id: uuid.UUID
    name: str
    in_use: bool  # has stock or sales history; can be merged but not removed


class BranchRename(BaseModel):
    name: NameText


class BranchMerge(BaseModel):
    into: uuid.UUID


@router.get("")
def list_branches(owner: User = Depends(owner_only), db: Session = Depends(get_session)) -> list[BranchOut]:
    branches = db.scalars(
        select(Branch).where(Branch.organization_id == owner.organization_id).order_by(Branch.created_at)
    ).all()
    used = _branches_in_use(db, owner.organization_id)
    return [BranchOut(id=branch.id, name=branch.name, in_use=branch.id in used) for branch in branches]


@router.patch("/{branch_id}")
def rename_branch(
    branch_id: uuid.UUID,
    body: BranchRename,
    owner: User = Depends(owner_only),
    db: Session = Depends(get_session),
) -> BranchOut:
    branch = _find(db, owner, branch_id, lock=True)
    _check_name_free(db, owner, body.name, exclude=branch.id)
    before = branch.name
    branch.name = body.name
    if branch.name != before:
        record_change(db, owner, "branch.renamed", "branch", branch.id, before={"name": before}, after={"name": branch.name})
    db.commit()
    return BranchOut(id=branch.id, name=branch.name, in_use=branch.id in _branches_in_use(db, owner.organization_id))


@router.post("/{branch_id}/merge", status_code=204)
def merge_branch(
    branch_id: uuid.UUID,
    body: BranchMerge,
    owner: User = Depends(owner_only),
    db: Session = Depends(get_session),
) -> None:
    """Moves every stock level and sale line from this branch into another one, then removes it."""
    source = _find(db, owner, branch_id, lock=True)
    target = _find(db, owner, body.into, lock=True)
    if source.id == target.id:
        raise HTTPException(422, "Choose a different branch to merge into.")

    target_levels = {
        level.part_id: level
        for level in db.scalars(select(StockLevel).where(StockLevel.branch_id == target.id))
    }
    for level in db.scalars(select(StockLevel).where(StockLevel.branch_id == source.id)):
        kept = target_levels.get(level.part_id)
        if kept is None:
            level.branch_id = target.id
        else:
            kept.quantity += level.quantity
            db.delete(level)
    db.execute(update(SaleLine).where(SaleLine.branch_id == source.id).values(branch_id=target.id))
    db.execute(update(StockOut).where(StockOut.branch_id == source.id).values(branch_id=target.id))
    db.execute(delete(Forecast).where(Forecast.branch_id == source.id))  # remade on the next forecast run
    db.flush()

    names = {"from": source.name, "into": target.name}
    db.delete(source)
    record_change(db, owner, "branch.merged", "branch", target.id, after=names)
    db.commit()


@router.delete("/{branch_id}", status_code=204)
def remove_branch(branch_id: uuid.UUID, owner: User = Depends(owner_only), db: Session = Depends(get_session)) -> None:
    branch = _find(db, owner, branch_id, lock=True)
    if branch.id in _branches_in_use(db, owner.organization_id):
        raise HTTPException(409, "This branch has stock or sales history. Merge it into another branch first.")
    if _count(db, owner.organization_id) <= 1:
        raise HTTPException(409, NEEDS_ONE_BRANCH)

    record_change(db, owner, "branch.removed", "branch", branch.id, before={"name": branch.name})
    db.delete(branch)
    db.commit()


def _find(db: Session, owner: User, branch_id: uuid.UUID, lock: bool = False) -> Branch:
    query = select(Branch).where(Branch.id == branch_id, Branch.organization_id == owner.organization_id)
    branch = db.scalar(query.with_for_update() if lock else query)
    if branch is None:
        raise HTTPException(404, "This branch is not in your shop.")
    return branch


def _check_name_free(db: Session, owner: User, name: str, exclude: uuid.UUID) -> None:
    clash = db.scalar(
        select(Branch.id).where(
            Branch.organization_id == owner.organization_id, Branch.id != exclude, func.lower(Branch.name) == name.lower()
        )
    )
    if clash:
        raise HTTPException(409, "A branch with this name already exists.")


def _branches_in_use(db: Session, organization_id: uuid.UUID) -> set[uuid.UUID]:
    with_stock = db.scalars(
        select(StockLevel.branch_id).distinct().join(Branch).where(Branch.organization_id == organization_id)
    ).all()
    with_sales = db.scalars(
        select(SaleLine.branch_id).distinct().join(Branch).where(Branch.organization_id == organization_id)
    ).all()
    return set(with_stock) | set(with_sales)


def _count(db: Session, organization_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).select_from(Branch).where(Branch.organization_id == organization_id)) or 0
