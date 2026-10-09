"""Import all SQLAlchemy models so Base.metadata is complete for Alembic."""

from app.modules.auth.models import UserRole
from app.modules.roles.models import Role
from app.modules.users.models import User

__all__ = ["User", "Role", "UserRole"]
