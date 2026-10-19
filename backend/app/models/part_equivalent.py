import uuid
from typing import Literal

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

EquivalentSource = Literal["manual", "supplier_file"]
EQUIVALENT_SOURCES: tuple[EquivalentSource, ...] = ("manual", "supplier_file")


class PartEquivalent(Base):
    """Says two parts are the same part under another brand: a manager's link, or a row from a
    supplier's cross-reference file. Same-OEM-number equivalents are automatic and never stored
    here. part_a_id is always the smaller id, so the same pair is never stored twice."""

    __tablename__ = "part_equivalents"
    __table_args__ = (
        UniqueConstraint("organization_id", "part_a_id", "part_b_id", name="part_equivalents_pair_unique"),
        CheckConstraint("part_a_id < part_b_id", name="part_equivalents_ordered"),
        CheckConstraint("source IN ('manual', 'supplier_file')", name="part_equivalents_source_valid"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    part_a_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"))
    part_b_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"))
    source: Mapped[str] = mapped_column(String(20))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
