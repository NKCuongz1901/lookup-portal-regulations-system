"""Import all SQLAlchemy models so Base.metadata is complete for Alembic."""

from app.modules.auth.models import UserRole
from app.modules.documents.registry import (
    Document,
    DocumentRelation,
    DocumentSegment,
    DocumentTag,
    DocumentType,
    DocumentVersion,
    IssuingUnit,
    StoredFile,
    Tag,
)
from app.modules.roles.models import Role
from app.modules.users.models import User
from app.modules.extractions.models import ExtractionRun, ExtractedField, FieldEvidence

__all__ = [
    "User",
    "Role",
    "UserRole",
    "DocumentType",
    "IssuingUnit",
    "Tag",
    "StoredFile",
    "Document",
    "DocumentVersion",
    "DocumentRelation",
    "DocumentTag",
    "DocumentSegment",
    "ExtractionRun",
    "ExtractedField",
    "FieldEvidence",
]
