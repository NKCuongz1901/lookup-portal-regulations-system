"""SQLAlchemy 2.0 models for the document domain (5 tables).

All table and column names follow university_regulations_schema.dbml.
The lookup tables and StoredFile are defined in document_metadata/files.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.documents.enums import (
    DocumentParseStatus,
    DocumentPublicationStatus,
    DocumentRelationType,
    enum_values,
)

if TYPE_CHECKING:
    from app.modules.document_metadata.models import DocumentType, IssuingUnit, Tag
    from app.modules.files.models import StoredFile


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "effective_until IS NULL OR effective_from IS NULL "
            "OR effective_until >= effective_from",
            name="ck_documents_effective_dates",
        ),
        Index("ix_documents_document_type_id", "document_type_id"),
        Index("ix_documents_issuing_unit_id", "issuing_unit_id"),
        Index("ix_documents_academic_year", "academic_year"),
        Index("ix_documents_publication_effective", "publication_status", "effective_from"),
        Index("ix_documents_issue_expiry", "issue_date", "effective_until"),
        Index("ix_documents_created_by", "created_by"),
        Index("ix_documents_updated_by", "updated_by"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    document_type_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("document_types.id", ondelete="RESTRICT"), nullable=True
    )
    issuing_unit_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("issuing_units.id", ondelete="RESTRICT"), nullable=True
    )
    issue_date: Mapped[date | None] = mapped_column(Date)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_until: Mapped[date | None] = mapped_column(Date)
    academic_year: Mapped[str | None] = mapped_column(String(30))
    applicable_subject_codes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSONB),
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    publication_status: Mapped[DocumentPublicationStatus] = mapped_column(
        SAEnum(
            DocumentPublicationStatus,
            name="document_publication_status",
            values_callable=enum_values,
            native_enum=True,
        ),
        nullable=False,
        default=DocumentPublicationStatus.DRAFT,
        server_default=DocumentPublicationStatus.DRAFT.value,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )

    document_type: Mapped[DocumentType | None] = relationship(
        "DocumentType", back_populates="documents"
    )
    issuing_unit: Mapped[IssuingUnit | None] = relationship(
        "IssuingUnit", back_populates="documents"
    )
    # Keep version history protected by RESTRICT, including loaded versions.
    versions: Mapped[list[DocumentVersion]] = relationship(
        "DocumentVersion", back_populates="document", passive_deletes="all",
        order_by="DocumentVersion.version_number",
    )
    outgoing_relations: Mapped[list[DocumentRelation]] = relationship(
        "DocumentRelation", back_populates="source_document",
        foreign_keys="DocumentRelation.source_document_id",
        cascade="all, delete-orphan", passive_deletes=True,
    )
    incoming_relations: Mapped[list[DocumentRelation]] = relationship(
        "DocumentRelation", back_populates="target_document",
        foreign_keys="DocumentRelation.target_document_id",
        cascade="all, delete-orphan", passive_deletes=True,
    )
    document_tags: Mapped[list[DocumentTag]] = relationship(
        "DocumentTag", back_populates="document", cascade="all, delete-orphan",
        passive_deletes=True,
    )
    # A read-only convenience collection. Insert through DocumentTag.
    tags: Mapped[list[Tag]] = relationship(
        "Tag", secondary="document_tags", back_populates="documents", viewonly=True
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_versions_document_version"),
        CheckConstraint("version_number > 0", name="ck_document_versions_positive_version"),
        Index("ix_document_versions_document_current", "document_id", "is_current"),
        Index("ix_document_versions_file_id", "file_id"),
        Index("ix_document_versions_created_by", "created_by"),
        # Partial UNIQUE: allow many non-current versions, <= 1 current version.
        Index(
            "ux_document_versions_current", "document_id", unique=True,
            postgresql_where=text("is_current = TRUE"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    file_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stored_files.id", ondelete="RESTRICT"), nullable=False
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    parse_status: Mapped[DocumentParseStatus] = mapped_column(
        SAEnum(
            DocumentParseStatus,
            name="document_parse_status",
            values_callable=enum_values,
            native_enum=True,
        ),
        nullable=False,
        default=DocumentParseStatus.PENDING,
        server_default=DocumentParseStatus.PENDING.value,
    )
    parser_version: Mapped[str | None] = mapped_column(String(50))
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    document: Mapped[Document] = relationship("Document", back_populates="versions")
    file: Mapped[StoredFile] = relationship("StoredFile", back_populates="document_versions")
    segments: Mapped[list[DocumentSegment]] = relationship(
        "DocumentSegment", back_populates="document_version",
        cascade="all, delete-orphan", passive_deletes=True,
        order_by="DocumentSegment.segment_index",
    )


class DocumentRelation(Base):
    __tablename__ = "document_relations"
    __table_args__ = (
        UniqueConstraint(
            "source_document_id", "target_document_id", "relation_type",
            name="uq_document_relations_source_target_type",
        ),
        CheckConstraint(
            "source_document_id <> target_document_id",
            name="ck_document_relations_not_self",
        ),
        Index("ix_document_relations_target_type", "target_document_id", "relation_type"),
        Index("ix_document_relations_created_by", "created_by"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    target_document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[DocumentRelationType] = mapped_column(
        SAEnum(
            DocumentRelationType,
            name="document_relation_type",
            values_callable=enum_values,
            native_enum=True,
        ),
        nullable=False,
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    source_document: Mapped[Document] = relationship(
        "Document", back_populates="outgoing_relations", foreign_keys=[source_document_id]
    )
    target_document: Mapped[Document] = relationship(
        "Document", back_populates="incoming_relations", foreign_keys=[target_document_id]
    )


class DocumentTag(Base):
    __tablename__ = "document_tags"
    __table_args__ = (Index("ix_document_tags_tag_id", "tag_id"),)

    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    document: Mapped[Document] = relationship("Document", back_populates="document_tags")
    tag: Mapped[Tag] = relationship("Tag", back_populates="document_tags")


class DocumentSegment(Base):
    __tablename__ = "document_segments"
    __table_args__ = (
        UniqueConstraint(
            "document_version_id", "segment_index",
            name="uq_document_segments_version_index",
        ),
        Index("ix_document_segments_version_page", "document_version_id", "page_number"),
        CheckConstraint("segment_index >= 0", name="ck_document_segments_index_nonnegative"),
        CheckConstraint(
            "page_number IS NULL OR page_number > 0",
            name="ck_document_segments_page_positive",
        ),
        CheckConstraint(
            "char_start IS NULL OR char_start >= 0",
            name="ck_document_segments_start_nonnegative",
        ),
        CheckConstraint(
            "char_end IS NULL OR char_start IS NULL OR char_end >= char_start",
            name="ck_document_segments_valid_offsets",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_version_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False
    )
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    paragraph_index: Mapped[int | None] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    document_version: Mapped[DocumentVersion] = relationship(
        "DocumentVersion", back_populates="segments"
    )
