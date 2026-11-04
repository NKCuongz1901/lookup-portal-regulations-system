from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.schemas import RequestSchema
from app.modules.extractions.field_types import FieldKey


class RunQuery(RequestSchema):
    page: int = Field(default=1, ge=1)
    itemsPerPage: int = Field(default=10, ge=1, le=100)


class FieldQuery(RunQuery):
    field_key: FieldKey | None = None
    review_status: Literal["pending", "approved", "rejected"] | None = None


class RunCreate(RequestSchema):
    # Reuse this UUID for HTTP retries; a new UUID is an intentional new run.
    idempotency_key: UUID


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    document_version_id: int
    extraction_method: str
    rule_version: str
    parser_version: str | None
    source_parsed_at: datetime | None
    source_fingerprint: str
    status: Literal["pending", "processing", "completed", "failed"]
    attempt_count: int
    field_count: int
    warnings: list[str]
    error_code: str | None
    error_message: str | None
    requested_by: int | None
    lease_expires_at: datetime | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    document_segment_id: int | None
    source_segment_id: int
    segment_index: int
    page_number: int | None
    section_title: str | None
    segment_content_snapshot: str
    quote: str
    start_offset: int
    end_offset: int
    role: Literal["value", "context"]
    occurrence_index: int


class ExtractedFieldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    extraction_run_id: int
    field_key: FieldKey
    item_index: int
    raw_value: str
    normalized_value: dict[str, Any]
    rule_id: str
    rule_version: str
    review_status: Literal["pending", "approved", "rejected"]
    review_revision: int
    reviewed_value: str | None
    reviewed_at: datetime | None
    created_at: datetime
    evidences: list[EvidenceResponse]


class ReviewCreate(RequestSchema):
    action: Literal["approve", "correct", "reject"]
    expected_revision: int = Field(ge=0)
    idempotency_key: UUID
    corrected_value: str | None = Field(default=None, min_length=1, max_length=20000)
    note: str | None = Field(default=None, min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_action(self):
        if self.action == "correct" and self.corrected_value is None:
            raise ValueError("Corrected value is required")
        if self.action != "correct" and self.corrected_value is not None:
            raise ValueError("Only correct accepts a corrected value")
        if self.action in {"correct", "reject"} and not self.note:
            raise ValueError("A review note is required for correction or rejection")
        return self


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    extracted_field_id: int
    revision: int
    action: Literal["approve", "correct", "reject"]
    previous_status: str
    new_status: str
    previous_value: str
    new_value: str
    note: str | None
    reviewer_id: int | None
    reviewer_name: str
    created_at: datetime
