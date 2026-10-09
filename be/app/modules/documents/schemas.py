from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.core.schemas import PaginationQuery, PartialUpdate, RequestSchema
from app.modules.document_metadata.schemas import DocumentTypeResponse, IssuingUnitResponse, TagResponse
from app.modules.documents.enums import DocumentPublicationStatus


DocumentCode = Annotated[str, StringConstraints(min_length=1, max_length=100)]
DocumentTitle = Annotated[str, StringConstraints(min_length=1, max_length=500)]
AcademicYear = Annotated[str, StringConstraints(min_length=1, max_length=30)]
SubjectCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
RecordId = Annotated[int, Field(gt=0, le=9223372036854775807)]


class DocumentCreate(RequestSchema):
    code: DocumentCode
    title: DocumentTitle
    description: str | None = None
    document_type_id: RecordId | None = None
    issuing_unit_id: RecordId | None = None
    issue_date: date | None = None
    effective_from: date | None = None
    effective_until: date | None = None
    academic_year: AcademicYear | None = None
    applicable_subject_codes: list[SubjectCode] = Field(default_factory=list)
    tag_ids: list[RecordId] = Field(default_factory=list)

    @field_validator("tag_ids", "applicable_subject_codes")
    @classmethod
    def remove_duplicates(cls, values):
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def validate_effective_dates(self):
        if (
            self.effective_from is not None and self.effective_until is not None
            and self.effective_until < self.effective_from
        ):
            raise ValueError("effective_until must be on or after effective_from")
        return self


class DocumentUpdate(PartialUpdate):
    non_nullable_fields = frozenset({"code", "title", "applicable_subject_codes", "tag_ids"})
    code: DocumentCode | None = None
    title: DocumentTitle | None = None
    description: str | None = None
    document_type_id: RecordId | None = None
    issuing_unit_id: RecordId | None = None
    issue_date: date | None = None
    effective_from: date | None = None
    effective_until: date | None = None
    academic_year: AcademicYear | None = None
    applicable_subject_codes: list[SubjectCode] | None = None
    tag_ids: list[RecordId] | None = None

    @field_validator("tag_ids", "applicable_subject_codes")
    @classmethod
    def remove_duplicates(cls, values):
        return list(dict.fromkeys(values)) if values is not None else None


class DocumentFilter(PaginationQuery):
    document_type_id: RecordId | None = None
    issuing_unit_id: RecordId | None = None
    tag_id: RecordId | None = None
    academic_year: AcademicYear | None = None
    publication_status: DocumentPublicationStatus | None = None


class DocumentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    title: str
    document_type_id: int | None
    issuing_unit_id: int | None
    document_type: DocumentTypeResponse | None
    issuing_unit: IssuingUnitResponse | None
    tags: list[TagResponse]
    issue_date: date | None
    effective_from: date | None
    effective_until: date | None
    academic_year: str | None
    publication_status: DocumentPublicationStatus
    created_at: datetime
    updated_at: datetime


class DocumentDetail(DocumentListItem):
    description: str | None
    applicable_subject_codes: list[str]
    published_at: datetime | None
    created_by: int
    updated_by: int | None
