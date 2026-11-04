"""Human review with optimistic concurrency, idempotency and immutable audit rows."""
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.modules.documents.models import Document, DocumentVersion
from app.modules.extractions.models import ExtractedField, ExtractionRun, FieldReview
from app.modules.extractions.result_service import RunConflictError, RunNotFoundError
from app.modules.extractions.schemas import ReviewCreate
from app.modules.users.models import User


def get_field(db: Session, field_id: int, *, lock: bool = False) -> ExtractedField:
    statement = (select(ExtractedField).join(ExtractionRun).join(DocumentVersion).join(Document)
                 .where(ExtractedField.id == field_id, Document.deleted_at.is_(None))
                 .options(selectinload(ExtractedField.evidences)).execution_options(populate_existing=True))
    if lock:
        statement = statement.with_for_update(of=ExtractedField)
    field = db.scalar(statement)
    if field is None:
        raise RunNotFoundError("Extracted field not found")
    return field


def review_field(db: Session, field_id: int, payload: ReviewCreate, actor: User) -> ExtractedField:
    try:
        field = get_field(db, field_id, lock=True)
        if field.run.status != "completed":
            raise RunConflictError("Only completed extractions can be reviewed")
        fingerprint = hashlib.sha256(json.dumps(
            {**payload.model_dump(mode="json", exclude={"idempotency_key"}), "actor_id": actor.id},
            sort_keys=True, ensure_ascii=False,
        ).encode()).hexdigest()
        previous_request = db.scalar(select(FieldReview).where(
            FieldReview.extracted_field_id == field_id, FieldReview.request_key == str(payload.idempotency_key)))
        if previous_request:
            if previous_request.request_fingerprint != fingerprint:
                raise RunConflictError("Idempotency key was already used for a different review")
            db.commit()
            return field
        if field.review_revision != payload.expected_revision:
            raise RunConflictError("This field was reviewed by another request. Refresh before reviewing again.")
        previous_value = field.reviewed_value if field.reviewed_value is not None else field.raw_value
        new_value = payload.corrected_value if payload.action == "correct" else previous_value
        new_status = "rejected" if payload.action == "reject" else "approved"
        db.add(FieldReview(
            extracted_field_id=field.id, request_key=str(payload.idempotency_key), request_fingerprint=fingerprint,
            revision=field.review_revision + 1, action=payload.action,
            previous_status=field.review_status, new_status=new_status,
            previous_value=previous_value, new_value=new_value, note=payload.note,
            reviewer_id=actor.id, reviewer_name=actor.full_name,
        ))
        field.review_revision += 1
        field.review_status = new_status
        field.reviewed_at = datetime.now(timezone.utc)
        if payload.action == "correct":
            field.reviewed_value = payload.corrected_value
        # raw_value, normalized_value and all evidence remain the original proposal.
        db.commit()
        return field
    except Exception:
        db.rollback()
        raise


def list_reviews(db: Session, field_id: int, page: int, size: int):
    get_field(db, field_id)
    condition = FieldReview.extracted_field_id == field_id
    total = db.scalar(select(func.count()).select_from(FieldReview).where(condition)) or 0
    rows = db.scalars(select(FieldReview).where(condition).order_by(FieldReview.revision.desc())
                      .offset((page - 1) * size).limit(size)).all()
    return rows, total
