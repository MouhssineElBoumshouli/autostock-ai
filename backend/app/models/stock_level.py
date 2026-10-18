import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class StockLevel(Base):
    """How many of one part are on the shelf in one branch."""

    __tablename__ = "stock_levels"
    __table_args__ = (UniqueConstraint("part_id", "branch_id", name="stock_levels_part_branch_unique"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"))
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"))
    quantity: Mapped[int] = mapped_column(default=0)
