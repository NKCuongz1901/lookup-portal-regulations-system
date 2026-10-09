from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.modules.auth.schemas import LoginRequest, TokenResponse
from app.modules.users.models import User

INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Incorrect email or password",
    headers={"WWW-Authenticate": "Bearer"},
)


def login(db: Session, payload: LoginRequest) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))

    if user is None:
        raise INVALID_CREDENTIALS

    if not verify_password(payload.password, user.password_hash):
        raise INVALID_CREDENTIALS

    if not user.is_active:
        raise INVALID_CREDENTIALS

    access_token = create_access_token(user.id)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
