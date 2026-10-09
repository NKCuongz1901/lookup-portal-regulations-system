from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

import app.models  # noqa: F401
from app.core.database import get_db
from app.modules.auth.router import router as auth_router

app = FastAPI(
    title="University Regulations API",
    version="1.0.0",
    description="Regulations and Forms Management System",
)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth_router)
app.include_router(api_v1)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "Error"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "message": message,
            "status_code": exc.status_code,
            "data": None,
        },
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "message": "Validation error",
            "status_code": 422,
            "data": exc.errors(),
        },
    )


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "university-regulations-api",
    }


@app.get("/health/db")
def database_health_check(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT 1"))

    return {
        "status": "connected",
        "database": "PostgreSQL",
        "result": result.scalar_one(),
    }
