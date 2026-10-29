"""What the owner sees about backups in Settings: when the last good one was made, how many are
kept, and the last problem (a backup skipped because the disk was full...). Owners only.
While developing there are no backups (BACKUP_DIR is empty): `on` is false and Settings hides it."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.permissions import require_role
from app.backups import backup_folder, backup_status
from app.config import BACKUP_DIR
from app.models import User

router = APIRouter(prefix="/api/backups")
owner_only = require_role("owner")


class BackupsOut(BaseModel):
    on: bool
    last_good_at: datetime | None = None
    kept: int = 0
    problem: Literal["disk_full", "database_unreachable", "failed"] | None = None


@router.get("")
def read_backups(_owner: User = Depends(owner_only)) -> BackupsOut:
    if not BACKUP_DIR:
        return BackupsOut(on=False)
    status = backup_status(backup_folder())
    return BackupsOut(on=True, last_good_at=status.last_good_at, kept=status.kept, problem=status.problem)
