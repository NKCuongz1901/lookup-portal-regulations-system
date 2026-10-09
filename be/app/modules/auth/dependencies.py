from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from collections.abc import Callable

from app.core.database import get_db
from app.core.security import decode_access_token
from app.modules.auth.models import UserRole
from app.modules.users.models import User

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        user_id = decode_access_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.scalar(
        select(User)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
        .where(User.id == user_id)
    )

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

def require_roles(*roles: str) -> Callable[..., User]:
    allowed = set(roles)
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        user_role_codes = {ur.role.code for ur in current_user.user_roles}
        if user_role_codes.isdisjoint(allowed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return dependency