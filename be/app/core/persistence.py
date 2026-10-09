"""Translate PostgreSQL write conflicts without exposing database internals."""
from contextlib import contextmanager

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@contextmanager
def commit_or_rollback(db: Session):
    # Auth and validation may already have started the session transaction.
    try:
        yield
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        sqlstate = getattr(exc.orig, "sqlstate", None)
        if sqlstate == "23505":
            raise HTTPException(409, "A record with this unique value already exists") from exc
        if sqlstate == "23503":
            raise HTTPException(409, "Referenced data changed; reload and try again") from exc
        if sqlstate in {"23514", "23502"}:
            raise HTTPException(422, "Data violates a required field or constraint") from exc
        raise
    except Exception:
        db.rollback()
        raise
