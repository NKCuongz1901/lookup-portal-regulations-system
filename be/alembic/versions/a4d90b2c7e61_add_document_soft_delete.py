"""Track document soft deletion without removing files or version history.

Revision ID: a4d90b2c7e61
Revises: 7c4e9a2d6b10
"""
from alembic import op
import sqlalchemy as sa


revision = "a4d90b2c7e61"
down_revision = "7c4e9a2d6b10"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("deleted_by", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_documents_deleted_by_users", "documents", "users", ["deleted_by"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_documents_deleted_by", "documents", ["deleted_by"])


def downgrade():
    op.drop_index("ix_documents_deleted_by", table_name="documents")
    op.drop_constraint("fk_documents_deleted_by_users", "documents", type_="foreignkey")
    op.drop_column("documents", "deleted_by")
    op.drop_column("documents", "deleted_at")
