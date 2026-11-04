from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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
    created_at: datetime
    evidences: list[EvidenceResponse]
