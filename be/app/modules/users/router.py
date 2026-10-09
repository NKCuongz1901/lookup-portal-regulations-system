from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import ApiResponse, paginate, success
from app.modules.auth.dependencies import require_roles
from app.modules.users.models import User
from app.modules.users.schemas import UserCreateRequest, UserListItem
from app.modules.users.services import create_user, list_users

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=ApiResponse[list[UserListItem]])
def get_users(
    page: int = Query(1, ge=1),
    itemsPerPage: int = Query(10, ge=1, le=100),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN", "STAFF")),
):
    users, total = list_users(db, page, itemsPerPage, search)
    return success(
        data=[UserListItem.from_user(user) for user in users],
        message="OK",
        meta=paginate(page, itemsPerPage, total),
    )


@router.post(
    "",
    response_model=ApiResponse[UserListItem],
    status_code=status.HTTP_201_CREATED,
)
def create_user_endpoint(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN", "STAFF")),
):
    user = create_user(db, payload, current_user)
    return success(
        data=UserListItem.from_user(user),
        message="User created",
        status_code=201,
    )
