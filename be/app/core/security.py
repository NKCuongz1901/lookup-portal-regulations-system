from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(
    password: str,
    hashed_password: str
) -> bool:
    return password_hash.verify(
        password,
        hashed_password
    )


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc)
        + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        ),
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm="HS256",
    )

def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],  # hoặc ["HS256"]
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise ValueError("missing sub")
        return int(user_id)
    except (jwt.PyJWTError, ValueError):
        raise  # hoặc để dependency bắt