"""Seed default issuing units (đơn vị ban hành).

Run from the `be/` directory:

    python -m scripts.seed_issuing_units
"""

from sqlalchemy import select

import app.models  # noqa: F401 — register model relationships
from app.core.database import SessionLocal
from app.modules.document_metadata.models import IssuingUnit

DEFAULT_ISSUING_UNITS = (
    {"code": "DAU", "name": "Trường Đại học Kiến trúc Đà Nẵng"},
    {"code": "DTAO", "name": "Phòng Đào tạo"},
    {"code": "CTSV", "name": "Phòng Công tác Sinh viên"},
)


def seed_issuing_units() -> None:
    db = SessionLocal()

    try:
        created = 0
        skipped = 0

        for unit_data in DEFAULT_ISSUING_UNITS:
            existing = db.scalar(
                select(IssuingUnit).where(IssuingUnit.code == unit_data["code"])
            )

            if existing is not None:
                print(f"skip  {unit_data['code']} (already exists)")
                skipped += 1
                continue

            db.add(IssuingUnit(**unit_data, is_active=True))
            print(f"create {unit_data['code']} — {unit_data['name']}")
            created += 1

        db.commit()
        print(f"done: created={created}, skipped={skipped}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_issuing_units()
