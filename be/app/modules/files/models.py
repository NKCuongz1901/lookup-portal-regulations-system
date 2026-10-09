"""Metadata of uploaded PDF/DOCX files; file bytes live outside PostgreSQL."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.modules.documents.models import DocumentVersion


class StoredFile(Base):
    __tablename__ = "stored_files"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="ck_stored_files_size_nonnegative"),
        Index("ix_stored_files_checksum_sha256", "checksum_sha256"),
        Index("ix_stored_files_uploaded_by", "uploaded_by"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    storage_provider: Mapped[str] = mapped_column(
        String(30), nullable=False, default="local", server_default=text("'local'")
    )
    storage_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    original_name: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(150), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(CHAR(64))
    uploaded_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Let PostgreSQL enforce RESTRICT even when this collection is loaded.
    document_versions: Mapped[list[DocumentVersion]] = relationship(
        "DocumentVersion", back_populates="file", passive_deletes="all"
    )
