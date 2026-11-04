"""Persisted extraction proposals and immutable source evidence snapshots."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"
    __table_args__ = (
        UniqueConstraint("document_version_id", "request_key", name="uq_extraction_runs_version_request"),
        CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed')", name="ck_extraction_runs_status"),
        CheckConstraint("attempt_count >= 0 AND field_count >= 0", name="ck_extraction_runs_counts"),
        Index("ix_extraction_runs_version_created", "document_version_id", "created_at", "id"),
        Index("ix_extraction_runs_status_lease", "status", "lease_expires_at"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_version_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("document_versions.id", ondelete="RESTRICT"), nullable=False)
    request_key: Mapped[str] = mapped_column(String(200), nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(30), nullable=False, default="rule_based", server_default="rule_based")
    rule_version: Mapped[str] = mapped_column(String(50), nullable=False)
    parser_version: Mapped[str | None] = mapped_column(String(50))
    source_parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    field_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    error_code: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(String(500))
    requested_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    execution_token: Mapped[str | None] = mapped_column(String(36))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fields: Mapped[list[ExtractedField]] = relationship("ExtractedField", back_populates="run", cascade="all, delete-orphan", passive_deletes=True)


class ExtractedField(Base):
    __tablename__ = "extracted_fields"
    __table_args__ = (
        UniqueConstraint("extraction_run_id", "field_key", "item_index", name="uq_extracted_fields_run_key_item"),
        CheckConstraint("field_key IN ('deadline', 'obligation', 'applicable_subject', 'legal_basis')", name="ck_extracted_fields_key"),
        CheckConstraint("review_status IN ('pending', 'approved', 'rejected')", name="ck_extracted_fields_review_status"),
        CheckConstraint("item_index >= 0", name="ck_extracted_fields_item_index"),
        Index("ix_extracted_fields_run_review", "extraction_run_id", "review_status"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    extraction_run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("extraction_runs.id", ondelete="CASCADE"), nullable=False)
    field_key: Mapped[str] = mapped_column(String(30), nullable=False)
    item_index: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(50), nullable=False)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    run: Mapped[ExtractionRun] = relationship("ExtractionRun", back_populates="fields")
    evidences: Mapped[list[FieldEvidence]] = relationship("FieldEvidence", back_populates="field", cascade="all, delete-orphan", passive_deletes=True, order_by="FieldEvidence.id")


class FieldEvidence(Base):
    __tablename__ = "field_evidences"
    __table_args__ = (
        UniqueConstraint("extracted_field_id", "occurrence_index", "role", "source_segment_id", "start_offset", "end_offset", name="uq_field_evidences_source_span"),
        CheckConstraint("role IN ('value', 'context')", name="ck_field_evidences_role"),
        CheckConstraint("segment_index >= 0 AND occurrence_index >= 0", name="ck_field_evidences_indices"),
        CheckConstraint("page_number IS NULL OR page_number > 0", name="ck_field_evidences_page"),
        CheckConstraint("start_offset >= 0 AND end_offset > start_offset AND end_offset <= char_length(segment_content_snapshot)", name="ck_field_evidences_offsets"),
        CheckConstraint("quote = substring(segment_content_snapshot FROM start_offset + 1 FOR end_offset - start_offset)", name="ck_field_evidences_quote"),
        Index("ix_field_evidences_segment", "document_segment_id"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    extracted_field_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("extracted_fields.id", ondelete="CASCADE"), nullable=False)
    document_segment_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("document_segments.id", ondelete="SET NULL"))
    source_segment_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Historical ID, intentionally not an FK.
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(String(500))
    segment_content_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    occurrence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    field: Mapped[ExtractedField] = relationship("ExtractedField", back_populates="evidences")
