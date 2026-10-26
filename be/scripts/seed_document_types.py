"""Seed default document types (loại văn bản).

Run from the `be/` directory:

    python -m scripts.seed_document_types
"""

from sqlalchemy import select

import app.models  # noqa: F401 — register model relationships
from app.core.database import SessionLocal
from app.modules.document_metadata.models import DocumentType

DEFAULT_DOCUMENT_TYPES = (
    {"code": "REGULATION", "name": "Quy chế"},
    {"code": "DECISION", "name": "Quyết định"},
    {"code": "NOTICE", "name": "Thông báo"},
    {"code": "GUIDELINE", "name": "Hướng dẫn"},
    {"code": "POLICY", "name": "Quy định"},
)


def seed_document_types() -> None:
    db = SessionLocal()

    try:
        created = 0
        skipped = 0

        for type_data in DEFAULT_DOCUMENT_TYPES:
            existing = db.scalar(
                select(DocumentType).where(DocumentType.code == type_data["code"])
            )

            if existing is not None:
                print(f"skip  {type_data['code']} (already exists)")
                skipped += 1
                continue

            db.add(DocumentType(**type_data, is_active=True))
            print(f"create {type_data['code']} — {type_data['name']}")
            created += 1

        db.commit()
        print(f"done: created={created}, skipped={skipped}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_document_types()
