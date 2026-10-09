from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginationMeta(BaseModel):
    page: int
    itemsPerPage: int
    total: int
    totalPages: int


class ApiResponse(BaseModel, Generic[T]):
    message: str
    status_code: int
    data: T | None = None
    meta: PaginationMeta | None = None


def paginate(page: int, items_per_page: int, total: int) -> PaginationMeta:
    total_pages = (
        (total + items_per_page - 1) // items_per_page if items_per_page else 0
    )
    return PaginationMeta(
        page=page,
        itemsPerPage=items_per_page,
        total=total,
        totalPages=total_pages,
    )


def success(
    data: Any = None,
    message: str = "Success",
    status_code: int = 200,
    meta: PaginationMeta | None = None,
) -> dict[str, Any]:
    return {
        "message": message,
        "status_code": status_code,
        "data": data,
        "meta": meta,
    }
