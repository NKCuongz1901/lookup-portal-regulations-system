"""Migration/model agreement and public schema contracts, without a DB server."""
from io import StringIO
from pathlib import Path
import re

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_mock_engine
from sqlalchemy.dialects.postgresql import dialect
from sqlalchemy.orm import configure_mappers

import app.models
from app.core.database import Base
from app.modules.extractions.models import FieldEvidence
from app.modules.extractions.schemas import RunResponse


TABLES = {"extraction_runs", "extracted_fields", "field_evidences"}


def revision():
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    result = ScriptDirectory.from_config(config).get_current_head()
    assert result == "b8f31d2c9a60"
    return ScriptDirectory.from_config(config).get_revision(result).module


def sql_for(operation):
    output = StringIO()
    with Operations.context(MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})):
        operation()
    return output.getvalue()


def normalize(sql):
    sql = sql.strip().rstrip(";")
    if sql.startswith("CREATE TABLE"):
        lines = sql.splitlines()
        sql = " ".join([lines[0], *sorted(line.strip().rstrip(",") for line in lines[1:-1]), lines[-1]])
    return re.sub(r"\s+", " ", sql).strip()


def test_migration_matches_models_and_registered_foreign_keys():
    configure_mappers()
    statements = []
    engine = create_mock_engine("postgresql+psycopg://", lambda sql, *a, **kw: statements.append(normalize(str(sql.compile(dialect=dialect())))))
    Base.metadata.create_all(engine, tables=[table for table in Base.metadata.sorted_tables if table.name in TABLES], checkfirst=False)
    # Metadata-level enum DDL belongs to the existing document migration.
    earlier_enums = ("CREATE TYPE document_parse_status ", "CREATE TYPE document_publication_status ", "CREATE TYPE document_relation_type ")
    statements = [sql for sql in statements if not sql.startswith(earlier_enums)]
    actual = [normalize(sql) for sql in sql_for(revision().upgrade).split(";") if sql.strip()]
    assert sorted(actual) == sorted(statements)
    assert revision().down_revision == "a4d90b2c7e61"
    assert "DROP " not in sql_for(revision().upgrade)


def test_evidence_is_retained_when_source_segments_are_deleted():
    column = FieldEvidence.__table__.c.document_segment_id
    assert column.nullable
    assert next(iter(column.foreign_keys)).ondelete == "SET NULL"
    assert not FieldEvidence.__table__.c.source_segment_id.foreign_keys
    assert not FieldEvidence.__table__.c.segment_content_snapshot.nullable
    sql = sql_for(revision().downgrade)
    assert sql.index("DROP TABLE field_evidences") < sql.index("DROP TABLE extracted_fields") < sql.index("DROP TABLE extraction_runs")
    assert "DROP TABLE document_segments" not in sql


def test_internal_lease_token_and_request_key_are_not_exposed():
    assert "execution_token" not in RunResponse.model_fields
    assert "request_key" not in RunResponse.model_fields
