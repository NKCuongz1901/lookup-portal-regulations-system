"""Human review values and append-only review history.

Revision ID: c9a42e7d0b13
Revises: b8f31d2c9a60
"""
from alembic import op
import sqlalchemy as sa

revision = "c9a42e7d0b13"
down_revision = "b8f31d2c9a60"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("extracted_fields", sa.Column("review_revision", sa.Integer(), server_default="0", nullable=False))
    op.add_column("extracted_fields", sa.Column("reviewed_value", sa.Text(), nullable=True))
    op.add_column("extracted_fields", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "field_reviews",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("extracted_field_id", sa.BigInteger(), nullable=False),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("previous_status", sa.String(20), nullable=False),
        sa.Column("new_status", sa.String(20), nullable=False),
        sa.Column("previous_value", sa.Text(), nullable=False),
        sa.Column("new_value", sa.Text(), nullable=False),
        sa.Column("note", sa.String(2000), nullable=True),
        sa.Column("reviewer_id", sa.BigInteger(), nullable=True),
        sa.Column("reviewer_name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["extracted_field_id"], ["extracted_fields.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("extracted_field_id", "request_key", name="uq_field_reviews_request"),
        sa.UniqueConstraint("extracted_field_id", "revision", name="uq_field_reviews_revision"),
        sa.CheckConstraint("action IN ('approve', 'correct', 'reject')", name="ck_field_reviews_action"),
        sa.CheckConstraint("revision > 0", name="ck_field_reviews_revision"),
        sa.CheckConstraint("previous_status IN ('pending', 'approved', 'rejected') AND new_status IN ('approved', 'rejected')", name="ck_field_reviews_status"),
    )


def downgrade():
    op.drop_table("field_reviews")
    op.drop_column("extracted_fields", "reviewed_at")
    op.drop_column("extracted_fields", "reviewed_value")
    op.drop_column("extracted_fields", "review_revision")
