import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AskedQuestion(Base):
    """One question someone asked on the Ask page, with the answer they got, so the page can show
    their last questions when they come back. Only each person's newest KEPT_PER_PERSON are kept."""

    __tablename__ = "asked_questions"
    __table_args__ = (Index("ix_asked_questions_user", "organization_id", "user_id", "created_at"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    question: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(20))  # "assistant" (written answer) or "rule" (AI off)
    answer: Mapped[dict] = mapped_column(JSONB)  # what the page showed: the "done" event, or the rule answer
