"""Settings > "Download all my data": one .xlsx with every table, for the owner only."""

import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.audit import record_change
from app.auth.permissions import require_role
from app.db import get_session
from app.exports.build import build_export
from app.models import User

router = APIRouter(prefix="/api/exports")
owner_only = require_role("owner")

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/data")
def export_data(owner: User = Depends(owner_only), db: Session = Depends(get_session)) -> Response:
    buffer, file_name = build_export(db, owner.organization_id)
    record_change(db, owner, "data.exported", "export", uuid.uuid4())
    db.commit()
    return Response(
        content=buffer.getvalue(),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(file_name)}"},
    )
