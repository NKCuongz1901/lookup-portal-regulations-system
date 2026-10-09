from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import ApiResponse, success
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import LoginRequest, TokenResponse, UserMeResponse
from app.modules.auth.services import login
from app.modules.users.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=ApiResponse[TokenResponse])
def login_endpoint(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    token = login(db, payload)
    return success(data=token, message="Login successful")


@router.get("/me", response_model=ApiResponse[UserMeResponse])
def me(current_user: User = Depends(get_current_user)):
    return success(
        data=UserMeResponse.from_user(current_user),
        message="OK",
    )
