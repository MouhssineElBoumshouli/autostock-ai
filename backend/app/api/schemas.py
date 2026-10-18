"""Shapes of data sent to and from the website."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.models import Role, User


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: Role
    is_active: bool
    last_login_at: datetime | None

    @classmethod
    def of(cls, user: User) -> "UserOut":
        return cls.model_validate(user, from_attributes=True)


class OrganizationOut(BaseModel):
    id: uuid.UUID
    name: str


class Me(BaseModel):
    user: UserOut
    organization: OrganizationOut


NameText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
EmailText = Annotated[str, StringConstraints(max_length=320)]
PasswordText = Annotated[str, StringConstraints(max_length=200)]
