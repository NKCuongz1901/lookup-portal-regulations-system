from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.security import hash_password
from app.modules.auth.models import UserRole
from app.modules.roles.models import Role
from app.modules.users.models import User
from app.modules.users.schemas import UserCreateRequest


def list_users(
    db: Session,
    page: int,
    items_per_page: int,
    search: str | None = None,
) -> tuple[list[User], int]:
    stmt = (
        select(User)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
        .order_by(User.id)
    )
    count_stmt = select(func.count()).select_from(User)

    if search and search.strip():
        pattern = f"%{search.strip()}%"
        filters = or_(
            User.email.ilike(pattern),
            User.student_code.ilike(pattern),
        )
        stmt = stmt.where(filters)
        count_stmt = count_stmt.where(filters)

    total = db.scalar(count_stmt) or 0
    users = list(
        db.scalars(
            stmt.offset((page - 1) * items_per_page).limit(items_per_page)
        ).all()
    )
    return users, total


def _get_user_with_roles(db: Session, user_id: int) -> User | None:
    return db.scalar(
        select(User)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
        .where(User.id == user_id)
    )


def create_user(
    db: Session,
    payload: UserCreateRequest,
    current_user: User,
) -> User:
    caller_roles = {ur.role.code for ur in current_user.user_roles}

    if "ADMIN" in caller_roles:
        allowed_targets = {"STAFF", "STUDENT"}
    elif "STAFF" in caller_roles:
        allowed_targets = {"STUDENT"}
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    if payload.role.value not in allowed_targets:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You cannot create a user with role {payload.role.value}",
        )

    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        )

    if payload.student_code and db.scalar(
        select(User).where(User.student_code == payload.student_code)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student code already exists",
        )

    role = db.scalar(select(Role).where(Role.code == payload.role.value))
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role not found",
        )

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        student_code=payload.student_code,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()

    created = _get_user_with_roles(db, user.id)
    if created is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load created user",
        )
    return created
