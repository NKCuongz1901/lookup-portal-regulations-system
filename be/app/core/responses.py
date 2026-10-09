from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    message: str
    status_code: int
    data: T | None = None


def success(
    data: Any = None,
    message: str = "Success",
    status_code: int = 200,
) -> dict[str, Any]:
    return {
        "message": message,
        "status_code": status_code,
        "data": data,
    }
