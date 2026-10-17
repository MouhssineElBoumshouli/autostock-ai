"""Health check: tells the website (and people) if the server and database are up."""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_session

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"]
    database: Literal["reachable", "unreachable"]


def database_is_reachable(session: Session) -> bool:
    try:
        session.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


@router.get("/api/health")
def health(session: Session = Depends(get_session)) -> HealthResponse:
    reachable = database_is_reachable(session)
    return HealthResponse(status="ok", database="reachable" if reachable else "unreachable")
