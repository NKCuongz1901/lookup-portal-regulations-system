"""Create document management tables.

Revision ID: 7c4e9a2d6b10
Revises: e556d8322725
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "7c4e9a2d6b10"
down_revision: Union[str, Sequence[str], None] = "e556d8322725"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create nine document tables and their PostgreSQL enums and indexes."""
    op.create_table('document_types',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_table('issuing_units',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_table('tags',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=120), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_table('documents',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('document_type_id', sa.BigInteger(), nullable=True),
        sa.Column('issuing_unit_id', sa.BigInteger(), nullable=True),
        sa.Column('issue_date', sa.Date(), nullable=True),
        sa.Column('effective_from', sa.Date(), nullable=True),
        sa.Column('effective_until', sa.Date(), nullable=True),
        sa.Column('academic_year', sa.String(length=30), nullable=True),
        sa.Column('applicable_subject_codes', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('publication_status', sa.Enum('draft', 'published', 'hidden', 'archived', name='document_publication_status'), server_default='draft', nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.BigInteger(), nullable=False),
        sa.Column('updated_by', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('effective_until IS NULL OR effective_from IS NULL OR effective_until >= effective_from', name='ck_documents_effective_dates'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['document_type_id'], ['document_types.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['issuing_unit_id'], ['issuing_units.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_index('ix_documents_academic_year', 'documents', ['academic_year'], unique=False)
    op.create_index('ix_documents_created_by', 'documents', ['created_by'], unique=False)
    op.create_index('ix_documents_document_type_id', 'documents', ['document_type_id'], unique=False)
    op.create_index('ix_documents_issue_expiry', 'documents', ['issue_date', 'effective_until'], unique=False)
    op.create_index('ix_documents_issuing_unit_id', 'documents', ['issuing_unit_id'], unique=False)
    op.create_index('ix_documents_publication_effective', 'documents', ['publication_status', 'effective_from'], unique=False)
    op.create_index('ix_documents_updated_by', 'documents', ['updated_by'], unique=False)
    op.create_table('stored_files',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('storage_provider', sa.String(length=30), server_default=sa.text("'local'"), nullable=False),
        sa.Column('storage_key', sa.Text(), nullable=False),
        sa.Column('original_name', sa.String(length=500), nullable=False),
        sa.Column('mime_type', sa.String(length=150), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('checksum_sha256', sa.CHAR(length=64), nullable=True),
        sa.Column('uploaded_by', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('size_bytes >= 0', name='ck_stored_files_size_nonnegative'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('storage_key')
    )
    op.create_index('ix_stored_files_checksum_sha256', 'stored_files', ['checksum_sha256'], unique=False)
    op.create_index('ix_stored_files_uploaded_by', 'stored_files', ['uploaded_by'], unique=False)
    op.create_table('document_relations',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('source_document_id', sa.BigInteger(), nullable=False),
        sa.Column('target_document_id', sa.BigInteger(), nullable=False),
        sa.Column('relation_type', sa.Enum('replaced_by', 'amended_by', 'refers_to', 'related_to', name='document_relation_type'), nullable=False),
        sa.Column('created_by', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('source_document_id <> target_document_id', name='ck_document_relations_not_self'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['source_document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_document_id', 'target_document_id', 'relation_type', name='uq_document_relations_source_target_type')
    )
    op.create_index('ix_document_relations_created_by', 'document_relations', ['created_by'], unique=False)
    op.create_index('ix_document_relations_target_type', 'document_relations', ['target_document_id', 'relation_type'], unique=False)
    op.create_table('document_tags',
        sa.Column('document_id', sa.BigInteger(), nullable=False),
        sa.Column('tag_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('document_id', 'tag_id')
    )
    op.create_index('ix_document_tags_tag_id', 'document_tags', ['tag_id'], unique=False)
    op.create_table('document_versions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.BigInteger(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('file_id', sa.BigInteger(), nullable=False),
        sa.Column('is_current', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('parse_status', sa.Enum('pending', 'processing', 'parsed', 'failed', name='document_parse_status'), server_default='pending', nullable=False),
        sa.Column('parser_version', sa.String(length=50), nullable=True),
        sa.Column('parsed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('version_number > 0', name='ck_document_versions_positive_version'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['file_id'], ['stored_files.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id', 'version_number', name='uq_document_versions_document_version')
    )
    op.create_index('ix_document_versions_created_by', 'document_versions', ['created_by'], unique=False)
    op.create_index('ix_document_versions_document_current', 'document_versions', ['document_id', 'is_current'], unique=False)
    op.create_index('ix_document_versions_file_id', 'document_versions', ['file_id'], unique=False)
    op.create_index('ux_document_versions_current', 'document_versions', ['document_id'], unique=True, postgresql_where=sa.text('is_current = TRUE'))
    op.create_table('document_segments',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('document_version_id', sa.BigInteger(), nullable=False),
        sa.Column('segment_index', sa.Integer(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('paragraph_index', sa.Integer(), nullable=True),
        sa.Column('section_title', sa.String(length=500), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('char_start', sa.Integer(), nullable=True),
        sa.Column('char_end', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('char_end IS NULL OR char_start IS NULL OR char_end >= char_start', name='ck_document_segments_valid_offsets'),
        sa.CheckConstraint('char_start IS NULL OR char_start >= 0', name='ck_document_segments_start_nonnegative'),
        sa.CheckConstraint('page_number IS NULL OR page_number > 0', name='ck_document_segments_page_positive'),
        sa.CheckConstraint('segment_index >= 0', name='ck_document_segments_index_nonnegative'),
        sa.ForeignKeyConstraint(['document_version_id'], ['document_versions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_version_id', 'segment_index', name='uq_document_segments_version_index')
    )
    op.create_index('ix_document_segments_version_page', 'document_segments', ['document_version_id', 'page_number'], unique=False)


def downgrade() -> None:
    """Drop document tables before removing their PostgreSQL enum types."""
    op.drop_index('ix_document_segments_version_page', table_name='document_segments')
    op.drop_table('document_segments')
    op.drop_index('ux_document_versions_current', table_name='document_versions', postgresql_where=sa.text('is_current = TRUE'))
    op.drop_index('ix_document_versions_file_id', table_name='document_versions')
    op.drop_index('ix_document_versions_document_current', table_name='document_versions')
    op.drop_index('ix_document_versions_created_by', table_name='document_versions')
    op.drop_table('document_versions')
    op.drop_index('ix_document_tags_tag_id', table_name='document_tags')
    op.drop_table('document_tags')
    op.drop_index('ix_document_relations_target_type', table_name='document_relations')
    op.drop_index('ix_document_relations_created_by', table_name='document_relations')
    op.drop_table('document_relations')
    op.drop_index('ix_stored_files_uploaded_by', table_name='stored_files')
    op.drop_index('ix_stored_files_checksum_sha256', table_name='stored_files')
    op.drop_table('stored_files')
    op.drop_index('ix_documents_updated_by', table_name='documents')
    op.drop_index('ix_documents_publication_effective', table_name='documents')
    op.drop_index('ix_documents_issuing_unit_id', table_name='documents')
    op.drop_index('ix_documents_issue_expiry', table_name='documents')
    op.drop_index('ix_documents_document_type_id', table_name='documents')
    op.drop_index('ix_documents_created_by', table_name='documents')
    op.drop_index('ix_documents_academic_year', table_name='documents')
    op.drop_table('documents')
    op.drop_table('tags')
    op.drop_table('issuing_units')
    op.drop_table('document_types')

    bind = op.get_bind()
    for enum_name in (
        "document_parse_status",
        "document_relation_type",
        "document_publication_status",
    ):
        postgresql.ENUM(name=enum_name).drop(bind, checkfirst=True)
