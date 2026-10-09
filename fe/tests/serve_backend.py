"""Serve the real API with disposable PostgreSQL data for frontend smoke tests.

Run with the backend venv. All schema/data changes are rolled back on shutdown.
Only listens on loopback; never changes the application's existing tables.
"""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys
from threading import Lock
from uuid import uuid4

BACKEND = Path(__file__).resolve().parents[2] / "be"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

import uvicorn
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.core.security import hash_password
from app.main import app
from app.models import Document, DocumentType, IssuingUnit, Role, User, UserRole
from app.modules.documents.enums import DocumentPublicationStatus


def main():
    with engine.connect() as connection:
        transaction = connection.begin()
        previous_overrides = app.dependency_overrides.copy()
        try:
            schema = "test_regula_ui_" + uuid4().hex
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
            config = Config()
            config.set_main_option("script_location", str(BACKEND / "alembic"))
            with Operations.context(MigrationContext.configure(connection)):
                for revision in reversed(list(ScriptDirectory.from_config(config).walk_revisions())):
                    revision.module.upgrade()
            with Session(connection, join_transaction_mode="create_savepoint") as db:
                password_hash = hash_password("Regula-test-only-2026!")
                users = []
                for code, name in (("ADMIN", "Nguyễn Minh Anh"), ("STAFF", "Trần Hoài An"), ("STUDENT", "Lê Bảo Ngọc")):
                    role = Role(code=code, name=code)
                    user = User(email=f"test-{code.lower()}@example.com", full_name=name, password_hash=password_hash)
                    db.add_all([role, user])
                    db.flush()
                    db.add(UserRole(user=user, role=role))
                    users.append(user)
                kind = DocumentType(code="QC", name="Quy chế")
                unit = IssuingUnit(code="DT", name="Phòng Đào tạo")
                db.add_all([kind, unit])
                db.flush()
                titles = [
                    "Quy chế đào tạo trình độ đại học", "Quy định xét học bổng khuyến khích học tập",
                    "Hướng dẫn đăng ký học phần học kỳ I", "Quy định công tác sinh viên",
                    "Quy chế đánh giá kết quả rèn luyện", "Kế hoạch đào tạo năm học 2026–2027",
                    "Quy định sử dụng thư viện", "Hướng dẫn thực tập tốt nghiệp",
                    "Quy chế tổ chức thi kết thúc học phần", "Quy định miễn giảm học phí",
                    "Hướng dẫn xét công nhận tốt nghiệp", "Quy chế tuyển sinh đại học",
                ]
                statuses = list(DocumentPublicationStatus)
                for index, title in enumerate(titles):
                    created_at = datetime.now(timezone.utc) - timedelta(days=index * 13)
                    db.add(Document(
                        code=f"QC-2026-{index + 1:03}", title=title,
                        description="Dữ liệu kiểm thử giao diện, tự xóa khi dừng phiên kiểm thử.",
                        document_type_id=kind.id, issuing_unit_id=unit.id,
                        publication_status=statuses[index % len(statuses)],
                        issue_date=created_at.date(), academic_year="2026-2027",
                        applicable_subject_codes=["STUDENT"], created_by=users[0].id,
                        created_at=created_at, updated_at=created_at,
                    ))
                db.commit()
            lock = Lock()

            def test_db():
                # Concurrent dashboard reads share one rollback-only connection.
                with lock, Session(connection, autoflush=False, expire_on_commit=False,
                                   join_transaction_mode="create_savepoint") as db:
                    yield db

            app.dependency_overrides[get_db] = test_db
            print("Temporary frontend test API ready on http://127.0.0.1:8001", flush=True)
            uvicorn.run(app, host="127.0.0.1", port=8001, log_level="warning")
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous_overrides)
            transaction.rollback()
            print("Frontend test schema rolled back.", flush=True)


if __name__ == "__main__":
    main()
