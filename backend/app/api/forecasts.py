"""Forecasts: remake them on demand, and see how the last run went. (Screens come in a later step.)"""

import uuid
from datetime import date, datetime

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_change
from app.auth.permissions import require_role
from app.db import get_session
from app.forecast.run import run_forecasts_in_background
from app.models import ForecastRun, User

router = APIRouter(prefix="/api/forecasts")
managers = require_role("owner", "manager")
anyone = require_role()


class RunOut(BaseModel):
    trigger: str
    status: str
    seconds: float
    series_count: int
    history_last_day: date | None
    created_at: datetime


@router.post("/run", status_code=202)
def run_now(background: BackgroundTasks, user: User = Depends(managers), db: Session = Depends(get_session)) -> dict:
    """Starts a new forecast run. It takes up to a minute; the answer comes back at once."""
    record_change(db, user, "forecast.requested", "forecast_run", uuid.uuid4())
    db.commit()
    background.add_task(run_forecasts_in_background, user.organization_id, "manual")
    return {"status": "started"}


@router.get("/runs/latest")
def latest_run(user: User = Depends(anyone), db: Session = Depends(get_session)) -> RunOut | None:
    run = db.scalar(
        select(ForecastRun)
        .where(ForecastRun.organization_id == user.organization_id)
        .order_by(ForecastRun.created_at.desc())
        .limit(1)
    )
    return RunOut.model_validate(run, from_attributes=True) if run else None
