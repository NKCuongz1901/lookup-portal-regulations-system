"""Document lookup tables (document_types, issuing_units, tags)."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.modules.documents.models import Document, DocumentTag


class DocumentType(Base):
    __tablename__ = "document_types"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Do not null foreign keys on loaded documents when deleting this lookup.
    documents: Mapped[list[Document]] = relationship(
        "Document", back_populates="document_type", passive_deletes="all"
    )


class IssuingUnit(Base):
    __tablename__ = "issuing_units"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Preserve the database's RESTRICT behavior for loaded documents too.
    documents: Mapped[list[Document]] = relationship(
        "Document", back_populates="issuing_unit", passive_deletes="all"
    )


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Write through DocumentTag(document_id=..., tag_id=...).
    document_tags: Mapped[list[DocumentTag]] = relationship(
        "DocumentTag", back_populates="tag", cascade="all, delete-orphan",
        passive_deletes=True
    )
    documents: Mapped[list[Document]] = relationship(
        "Document", secondary="document_tags", back_populates="tags", viewonly=True
    )
