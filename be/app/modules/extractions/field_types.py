"""Step 4.3 contracts. All offsets are half-open Python character offsets."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


FieldKey = Literal["deadline", "obligation", "applicable_subject", "legal_basis"]
RULE_VERSION = "fields-1.0"


@dataclass(frozen=True)
class FieldSegment:
    segment_index: int
    content: str
    id: int | None = None  # None only for a dry run before segment persistence.
    page_number: int | None = None
    section_title: str | None = None


@dataclass(frozen=True)
class RuleMatch:
    field_key: FieldKey
    rule_id: str
    start: int
    end: int
    normalized_value: dict[str, Any]
    context_start: int
    context_end: int


@dataclass(frozen=True)
class FieldEvidence:
    document_segment_id: int | None
    segment_index: int
    page_number: int | None
    section_title: str | None
    start_offset: int  # Relative to the persisted segment.content, not full_text.
    end_offset: int
    quote: str
    role: Literal["value", "context"]
    occurrence_index: int


@dataclass(frozen=True)
class FieldCandidate:
    field_key: FieldKey
    item_index: int  # Zero-based within this field_key, in source order.
    raw_value: str
    normalized_value: dict[str, Any]
    rule_id: str
    evidences: tuple[FieldEvidence, ...]
    rule_version: str = RULE_VERSION
    review_status: str = "pending"


@dataclass(frozen=True)
class FieldExtractionResult:
    document_version_id: int | None
    candidates: tuple[FieldCandidate, ...]
    segment_count: int
    warnings: tuple[str, ...] = ()
    rule_version: str = RULE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
