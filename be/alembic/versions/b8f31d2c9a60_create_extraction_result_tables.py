"""Store rule extraction runs, fields and durable evidence snapshots.

Revision ID: b8f31d2c9a60
Revises: a4d90b2c7e61
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b8f31d2c9a60"
down_revision = "a4d90b2c7e61"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "extraction_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("document_version_id", sa.BigInteger(), nullable=False),
        sa.Column("request_key", sa.String(200), nullable=False),
        sa.Column("extraction_method", sa.String(30), server_default="rule_based", nullable=False),
        sa.Column("rule_version", sa.String(50), nullable=False),
        sa.Column("parser_version", sa.String(50), nullable=True),
        sa.Column("source_parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("field_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("warnings", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("requested_by", sa.BigInteger(), nullable=True),
        sa.Column("execution_token", sa.String(36), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("document_version_id", "request_key", name="uq_extraction_runs_version_request"),
        sa.CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed')", name="ck_extraction_runs_status"),
        sa.CheckConstraint("attempt_count >= 0 AND field_count >= 0", name="ck_extraction_runs_counts"),
    )
    op.create_index("ix_extraction_runs_version_created", "extraction_runs", ["document_version_id", "created_at", "id"])
    op.create_index("ix_extraction_runs_status_lease", "extraction_runs", ["status", "lease_expires_at"])
    op.create_table(
        "extracted_fields",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("extraction_run_id", sa.BigInteger(), nullable=False),
        sa.Column("field_key", sa.String(30), nullable=False),
        sa.Column("item_index", sa.Integer(), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=False),
        sa.Column("normalized_value", postgresql.JSONB(), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("rule_version", sa.String(50), nullable=False),
        sa.Column("review_status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["extraction_run_id"], ["extraction_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("extraction_run_id", "field_key", "item_index", name="uq_extracted_fields_run_key_item"),
        sa.CheckConstraint("field_key IN ('deadline', 'obligation', 'applicable_subject', 'legal_basis')", name="ck_extracted_fields_key"),
        sa.CheckConstraint("review_status IN ('pending', 'approved', 'rejected')", name="ck_extracted_fields_review_status"),
        sa.CheckConstraint("item_index >= 0", name="ck_extracted_fields_item_index"),
    )
    op.create_index("ix_extracted_fields_run_review", "extracted_fields", ["extraction_run_id", "review_status"])
    op.create_table(
        "field_evidences",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("extracted_field_id", sa.BigInteger(), nullable=False),
        sa.Column("document_segment_id", sa.BigInteger(), nullable=True),
        sa.Column("source_segment_id", sa.BigInteger(), nullable=False),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_title", sa.String(500), nullable=True),
        sa.Column("segment_content_snapshot", sa.Text(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("occurrence_index", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["extracted_field_id"], ["extracted_fields.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_segment_id"], ["document_segments.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("extracted_field_id", "occurrence_index", "role", "source_segment_id", "start_offset", "end_offset", name="uq_field_evidences_source_span"),
        sa.CheckConstraint("role IN ('value', 'context')", name="ck_field_evidences_role"),
        sa.CheckConstraint("segment_index >= 0 AND occurrence_index >= 0", name="ck_field_evidences_indices"),
        sa.CheckConstraint("page_number IS NULL OR page_number > 0", name="ck_field_evidences_page"),
        sa.CheckConstraint("start_offset >= 0 AND end_offset > start_offset AND end_offset <= char_length(segment_content_snapshot)", name="ck_field_evidences_offsets"),
        sa.CheckConstraint("quote = substring(segment_content_snapshot FROM start_offset + 1 FOR end_offset - start_offset)", name="ck_field_evidences_quote"),
    )
    op.create_index("ix_field_evidences_segment", "field_evidences", ["document_segment_id"])


def downgrade():
    op.drop_table("field_evidences")
    op.drop_table("extracted_fields")
    op.drop_table("extraction_runs")
