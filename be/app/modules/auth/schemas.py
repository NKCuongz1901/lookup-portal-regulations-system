from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, EmailStr

if TYPE_CHECKING:
    from app.modules.users.models import User


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserMeResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    student_code: str | None
    is_active: bool
    roles: list[str]

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_user(cls, user: "User") -> "UserMeResponse":
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            student_code=user.student_code,
            is_active=user.is_active,
            roles=[ur.role.code for ur in user.user_roles],
        )
