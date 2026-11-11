import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

Role = Literal["owner", "manager", "staff"]
ROLES: tuple[Role, ...] = ("owner", "manager", "staff")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'manager', 'staff')", name="users_role_valid"),
        CheckConstraint("language IS NULL OR language IN ('en', 'fr', 'ar')", name="users_language_valid"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    # Stored in lowercase. Unique across all shops, because people log in with email only.
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(default=True)
    # True when the owner chose the password (new person or reset): they must pick their own first.
    must_change_password: Mapped[bool] = mapped_column(default=False, server_default="false")
    last_login_at: Mapped[datetime | None]
    # None = the shop's language.
    language: Mapped[str | None] = mapped_column(String(2))

    def snapshot(self) -> dict:
        """What the audit log stores about a user. Never includes the password hash."""
        return {"name": self.name, "email": self.email, "role": self.role, "is_active": self.is_active}
