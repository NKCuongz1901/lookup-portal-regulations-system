"""Seed default roles: STUDENT, STAFF, ADMIN.

Run from the `be/` directory:

    python -m scripts.seed_roles
"""

from sqlalchemy import select

import app.models  # noqa: F401 — register User/Role/UserRole relationships
from app.core.database import SessionLocal
from app.modules.roles.models import Role

DEFAULT_ROLES = (
    {
        "code": "STUDENT",
        "name": "Student",
        "description": "Search regulations and forms",
    },
    {
        "code": "STAFF",
        "name": "Staff",
        "description": "Manage documents and approve AI data",
    },
    {
        "code": "ADMIN",
        "name": "Administrator",
        "description": "Manage users and system configuration",
    },
)


def seed_roles() -> None:
    db = SessionLocal()

    try:
        created = 0
        skipped = 0

        for role_data in DEFAULT_ROLES:
            existing = db.scalar(
                select(Role).where(Role.code == role_data["code"])
            )

            if existing is not None:
                print(f"skip  {role_data['code']} (already exists)")
                skipped += 1
                continue

            db.add(Role(**role_data))
            print(f"create {role_data['code']}")
            created += 1

        db.commit()
        print(f"done: created={created}, skipped={skipped}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_roles()
