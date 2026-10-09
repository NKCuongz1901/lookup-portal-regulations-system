from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.schemas import PaginationQuery, PartialUpdate, RequestSchema


LookupCode = Annotated[str, StringConstraints(min_length=1, max_length=50)]
TypeName = Annotated[str, StringConstraints(min_length=1, max_length=150)]
UnitName = Annotated[str, StringConstraints(min_length=1, max_length=255)]
TagName = Annotated[str, StringConstraints(min_length=1, max_length=100)]
TagSlug = Annotated[
    str, StringConstraints(min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
]


class DocumentTypeCreate(RequestSchema):
    code: LookupCode
    name: TypeName
    description: str | None = None
    is_active: bool = True


class DocumentTypeUpdate(PartialUpdate):
    non_nullable_fields = frozenset({"code", "name", "is_active"})
    code: LookupCode | None = None
    name: TypeName | None = None
    description: str | None = None
    is_active: bool | None = None


class IssuingUnitCreate(RequestSchema):
    code: LookupCode
    name: UnitName
    description: str | None = None
    is_active: bool = True


class IssuingUnitUpdate(PartialUpdate):
    non_nullable_fields = frozenset({"code", "name", "is_active"})
    code: LookupCode | None = None
    name: UnitName | None = None
    description: str | None = None
    is_active: bool | None = None


class TagCreate(RequestSchema):
    name: TagName
    slug: TagSlug


class TagUpdate(PartialUpdate):
    non_nullable_fields = frozenset({"name", "slug"})
    name: TagName | None = None
    slug: TagSlug | None = None


class LookupFilter(PaginationQuery):
    is_active: bool | None = Field(default=None)


class DocumentTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    description: str | None
    is_active: bool
    created_at: datetime


class IssuingUnitResponse(DocumentTypeResponse):
    pass


class TagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    created_at: datetime
