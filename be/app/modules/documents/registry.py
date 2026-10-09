"""Import this module before Alembic autogenerate to register all document tables."""
# ruff: noqa: F401
from app.modules.document_metadata.models import DocumentType, IssuingUnit, Tag
from app.modules.files.models import StoredFile
from app.modules.documents.models import (
    Document,
    DocumentVersion,
    DocumentRelation,
    DocumentTag,
    DocumentSegment,
)
