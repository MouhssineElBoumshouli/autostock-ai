import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ImportMapping(Base):
    """The last column matching a shop used for one kind of file, to pre-fill the next import.

    mapping: {"normalized column header": "field"}.
    """

    __tablename__ = "import_mappings"
    __table_args__ = (UniqueConstraint("organization_id", "kind", name="import_mappings_kind_unique"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    kind: Mapped[str] = mapped_column(String(20))
    mapping: Mapped[dict] = mapped_column(JSONB)
