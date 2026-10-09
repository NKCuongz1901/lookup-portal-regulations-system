"""PostgreSQL-native enum values defined in university_regulations_schema.dbml."""
from enum import Enum


class DocumentPublicationStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    HIDDEN = "hidden"
    ARCHIVED = "archived"


class DocumentParseStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PARSED = "parsed"
    FAILED = "failed"


class DocumentRelationType(str, Enum):
    REPLACED_BY = "replaced_by"
    AMENDED_BY = "amended_by"
    REFERS_TO = "refers_to"
    RELATED_TO = "related_to"


def enum_values(enum_class: type[Enum]) -> list[str]:
    """Persist Enum.value (lowercase) rather than the Python member name."""
    return [member.value for member in enum_class]
