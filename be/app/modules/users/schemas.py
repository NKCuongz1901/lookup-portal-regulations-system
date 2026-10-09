from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

if TYPE_CHECKING:
    from app.modules.users.models import User


class AssignableRole(str, Enum):
    STAFF = "STAFF"
    STUDENT = "STUDENT"


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1)
    role: AssignableRole
    student_code: str | None = None

    @model_validator(mode="after")
    def validate_student_code(self) -> "UserCreateRequest":
        if self.role == AssignableRole.STUDENT:
            if not self.student_code or not self.student_code.strip():
                raise ValueError("student_code is required for STUDENT")
            self.student_code = self.student_code.strip()
        else:
            self.student_code = None
        return self


class UserListItem(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    student_code: str | None
    is_active: bool
    roles: list[str]

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_user(cls, user: "User") -> "UserListItem":
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            student_code=user.student_code,
            is_active=user.is_active,
            roles=[ur.role.code for ur in user.user_roles],
        )
