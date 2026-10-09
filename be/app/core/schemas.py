"""Shared validation for management API requests."""
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PartialUpdate(RequestSchema):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def reject_explicit_nulls(self):
        for name in self.model_fields_set & self.non_nullable_fields:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class PaginationQuery(RequestSchema):
    page: int = Field(default=1, ge=1)
    itemsPerPage: int = Field(default=10, ge=1, le=100)
    search: str | None = Field(default=None, max_length=200)
