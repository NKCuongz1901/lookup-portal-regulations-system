"""Verify the real model registry and PostgreSQL migration SQL without a server."""
from io import StringIO
from pathlib import Path
import re

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_mock_engine, inspect
from sqlalchemy.dialects.postgresql import dialect
from sqlalchemy.orm import configure_mappers, make_transient_to_detached

import app.models
from app.core.database import Base
from app.models import (
    Document,
    DocumentRelation,
    DocumentSegment,
    DocumentTag,
    DocumentType,
    DocumentVersion,
    IssuingUnit,
    StoredFile,
    Tag,
)
from app.modules.documents.enums import (
    DocumentParseStatus,
    DocumentPublicationStatus,
    DocumentRelationType,
)


DOCUMENT_TABLES = {
    "document_types", "issuing_units", "tags", "stored_files", "documents",
    "document_versions", "document_relations", "document_tags", "document_segments",
}


@pytest.fixture
def migration():
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    scripts = ScriptDirectory.from_config(config)
    revision = scripts.get_revision("7c4e9a2d6b10")
    assert revision.down_revision == "e556d8322725"
    return revision.module


def migration_sql(migrate):
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )
    with Operations.context(context):
        migrate()
    return output.getvalue()


def normalize_sql(sql):
    sql = sql.strip().rstrip(";")
    if sql.startswith("CREATE TABLE"):
        # Constraint declaration order does not affect a PostgreSQL table.
        lines = sql.splitlines()
        declarations = sorted(line.strip().rstrip(",") for line in lines[1:-1])
        sql = " ".join([lines[0], *declarations, lines[-1]])
    return re.sub(r"\s+", " ", sql).strip()


def test_models_register_alongside_auth_and_resolve_foreign_keys():
    configure_mappers()
    assert set(Base.metadata.tables) == DOCUMENT_TABLES | {"users", "roles", "user_roles"}
    for table_name in DOCUMENT_TABLES:
        for foreign_key in Base.metadata.tables[table_name].foreign_keys:
            assert foreign_key.column.table.metadata is Base.metadata


def test_relationships_link_document_graph():
    document_type = DocumentType(code="regulation", name="Quy định")
    issuing_unit = IssuingUnit(code="university", name="Trường")
    stored_file = StoredFile(
        storage_key="documents/regulation.docx", original_name="regulation.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=100,
    )
    document = Document(
        code="QD-01", title="Quy định đào tạo", created_by=1,
        document_type=document_type, issuing_unit=issuing_unit,
    )
    version = DocumentVersion(document=document, file=stored_file, version_number=1, created_by=1)
    segment = DocumentSegment(document_version=version, segment_index=0, content="Điều 1")
    tag = Tag(name="Đào tạo", slug="dao-tao")
    link = DocumentTag(document=document, tag=tag)
    replacement = Document(code="QD-02", title="Quy định mới", created_by=1)
    relation = DocumentRelation(
        source_document=document, target_document=replacement,
        relation_type=DocumentRelationType.REPLACED_BY, created_by=1,
    )

    assert document_type.documents == issuing_unit.documents == [document]
    assert document.versions == stored_file.document_versions == [version]
    assert version.segments == [segment]
    assert segment.page_number is None  # DOCX need not have page numbers.
    assert document.document_tags == tag.document_tags == [link]
    assert document.outgoing_relations == replacement.incoming_relations == [relation]
    assert inspect(Document).relationships.tags.viewonly
    assert inspect(Tag).relationships.documents.viewonly


def test_in_place_subject_code_changes_are_tracked():
    document = Document(id=1, applicable_subject_codes=["student"])
    make_transient_to_detached(document)
    assert not inspect(document).modified

    document.applicable_subject_codes.append("lecturer")

    assert inspect(document).modified
    assert inspect(document).attrs.applicable_subject_codes.history.added == [
        ["student", "lecturer"]
    ]


@pytest.mark.parametrize("column, enum_class", [
    (Document.__table__.c.publication_status, DocumentPublicationStatus),
    (DocumentVersion.__table__.c.parse_status, DocumentParseStatus),
    (DocumentRelation.__table__.c.relation_type, DocumentRelationType),
])
def test_enums_round_trip_using_lowercase_values(column, enum_class):
    pg_dialect = dialect()
    enum_type = column.type.dialect_impl(pg_dialect)
    encode = enum_type.bind_processor(pg_dialect)
    decode = enum_type.result_processor(pg_dialect, None)
    for member in enum_class:
        assert encode(member) == member.value
        assert decode(member.value) is member


def test_migration_ddl_matches_models(migration):
    statements = []
    mock_engine = create_mock_engine(
        "postgresql+psycopg://",
        lambda sql, *args, **kwargs: statements.append(
            normalize_sql(str(sql.compile(dialect=dialect())))
        ),
    )
    Base.metadata.create_all(
        mock_engine,
        tables=[table for table in Base.metadata.sorted_tables if table.name in DOCUMENT_TABLES],
        checkfirst=False,
    )
    actual = [normalize_sql(sql) for sql in migration_sql(migration.upgrade).split(";") if sql.strip()]
    assert sorted(actual) == sorted(statements)
    assert len(actual) == len(set(actual))  # No duplicate enum/index creation.
    assert (
        "CREATE UNIQUE INDEX ux_document_versions_current ON document_versions "
        "(document_id) WHERE is_current = TRUE"
    ) in actual


def test_downgrade_drops_dependents_before_parents_and_enums(migration):
    sql = migration_sql(migration.downgrade)
    for table_name in DOCUMENT_TABLES:
        assert sql.count(f"DROP TABLE {table_name};") == 1
        table = Base.metadata.tables[table_name]
        for foreign_key in table.foreign_keys:
            parent = foreign_key.column.table.name
            if parent in DOCUMENT_TABLES:
                assert sql.index(f"DROP TABLE {table_name};") < sql.index(f"DROP TABLE {parent};")
    for enum_name in ("document_publication_status", "document_parse_status", "document_relation_type"):
        assert sql.count(f"DROP TYPE {enum_name};") == 1
        assert sql.index(f"DROP TYPE {enum_name};") > sql.rindex("DROP TABLE ")
    for auth_table in ("users", "roles", "user_roles"):
        assert f"DROP TABLE {auth_table};" not in sql
