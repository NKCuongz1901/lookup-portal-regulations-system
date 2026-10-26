"""Seed default tags (thẻ phân loại).

Run from the `be/` directory:

    python -m scripts.seed_tags
"""

from sqlalchemy import select

import app.models  # noqa: F401 — register model relationships
from app.core.database import SessionLocal
from app.modules.document_metadata.models import Tag

DEFAULT_TAGS = (
    {"name": "Đào tạo", "slug": "dao-tao"},
    {"name": "Học phí", "slug": "hoc-phi"},
    {"name": "Học bổng", "slug": "hoc-bong"},
    {"name": "Tốt nghiệp", "slug": "tot-nghiep"},
    {"name": "Bảo lưu", "slug": "bao-luu"},
    {"name": "Thực tập", "slug": "thuc-tap"},
    {"name": "Xét học vụ", "slug": "xet-hoc-vu"},
)


def seed_tags() -> None:
    db = SessionLocal()

    try:
        created = 0
        skipped = 0

        for tag_data in DEFAULT_TAGS:
            existing = db.scalar(select(Tag).where(Tag.slug == tag_data["slug"]))

            if existing is not None:
                print(f"skip  {tag_data['slug']} (already exists)")
                skipped += 1
                continue

            db.add(Tag(**tag_data))
            print(f"create {tag_data['slug']} — {tag_data['name']}")
            created += 1

        db.commit()
        print(f"done: created={created}, skipped={skipped}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_tags()
