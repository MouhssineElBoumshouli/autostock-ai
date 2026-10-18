import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SynonymGroup(Base):
    """Words that mean the same part ("brake pads", "plaquettes de frein", "فحمات الفرامل"), per shop."""

    __tablename__ = "synonym_groups"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    words: Mapped[list[str]] = mapped_column(ARRAY(String(100)))
