"""Seed demo users: admin, staff, student (with roles).

Run from the `be/` directory (after seed_roles):

    python -m scripts.seed_roles
    python -m scripts.seed_user

Default password for all accounts: Password123!
"""

from sqlalchemy import select

import app.models  # noqa: F401 — register User/Role/UserRole relationships
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.modules.auth.models import UserRole
from app.modules.roles.models import Role
from app.modules.users.models import User

DEFAULT_PASSWORD = "Password123!"

DEFAULT_USERS = (
    {
        "email": "admin@university.edu",
        "full_name": "System Administrator",
        "student_code": None,
        "role_code": "ADMIN",
    },
    {
        "email": "staff@university.edu",
        "full_name": "University Staff",
        "student_code": None,
        "role_code": "STAFF",
    },
    {
        "email": "student@university.edu",
        "full_name": "Demo Student",
        "student_code": "SV000001",
        "role_code": "STUDENT",
    },
)


def seed_users() -> None:
    db = SessionLocal()
    password_hashed = hash_password(DEFAULT_PASSWORD)

    try:
        created = 0
        skipped = 0

        for user_data in DEFAULT_USERS:
            role = db.scalar(
                select(Role).where(Role.code == user_data["role_code"])
            )
            if role is None:
                raise RuntimeError(
                    f"Role {user_data['role_code']} not found. "
                    "Run: python -m scripts.seed_roles"
                )

            existing = db.scalar(
                select(User).where(User.email == user_data["email"])
            )
            if existing is not None:
                print(f"skip  {user_data['email']} (already exists)")
                skipped += 1
                continue

            user = User(
                email=user_data["email"],
                password_hash=password_hashed,
                full_name=user_data["full_name"],
                student_code=user_data["student_code"],
                is_active=True,
            )
            db.add(user)
            db.flush()

            db.add(UserRole(user_id=user.id, role_id=role.id))
            print(f"create {user_data['email']} ({user_data['role_code']})")
            created += 1

        db.commit()
        print(f"done: created={created}, skipped={skipped}")
        print(f"password for all seeded users: {DEFAULT_PASSWORD}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_users()
