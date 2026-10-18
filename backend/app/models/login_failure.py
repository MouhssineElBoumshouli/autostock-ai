import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class LoginFailure(Base):
    """One wrong login. Counted per email to slow down password guessing.

    organization_id is empty when the email does not belong to anyone.
    """

    __tablename__ = "login_failures"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"))
    email: Mapped[str] = mapped_column(String(320), index=True)
