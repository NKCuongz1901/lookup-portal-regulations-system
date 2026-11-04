from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import ApiResponse, paginate, success
from app.modules.auth.dependencies import require_roles
from app.modules.extractions import result_service
from app.modules.extractions.schemas import ExtractedFieldResponse, FieldQuery, RunCreate, RunQuery, RunResponse
from app.modules.extractions.segment_service import VersionNotFoundError
from app.modules.extractions.tasks import enqueue_field_extraction
from app.modules.users.models import User


router = APIRouter(tags=["extractions"])
DB = Annotated[Session, Depends(get_db)]
Editor = Annotated[User, Depends(require_roles("ADMIN", "STAFF"))]
RecordId = Annotated[int, Path(gt=0, le=9223372036854775807)]


@contextmanager
def api_errors():
    try:
        yield
    except (VersionNotFoundError, result_service.RunNotFoundError) as error:
        raise HTTPException(404, str(error)) from error
    except result_service.RunConflictError as error:
        raise HTTPException(409, str(error)) from error


@router.get("/document-versions/{version_id}/extraction-runs", response_model=ApiResponse[list[RunResponse]])
def list_extraction_runs(version_id: RecordId, filters: Annotated[RunQuery, Query()], db: DB, actor: Editor):
    with api_errors():
        rows, total = result_service.list_runs(db, version_id, filters.page, filters.itemsPerPage)
        return success(data=[RunResponse.model_validate(row) for row in rows],
                       meta=paginate(filters.page, filters.itemsPerPage, total))


@router.get("/extraction-runs/{run_id}", response_model=ApiResponse[RunResponse])
def get_extraction_run(run_id: RecordId, db: DB, actor: Editor):
    with api_errors():
        return success(data=RunResponse.model_validate(result_service.get_run(db, run_id)))


@router.get("/extraction-runs/{run_id}/fields", response_model=ApiResponse[list[ExtractedFieldResponse]])
def list_extracted_fields(run_id: RecordId, filters: Annotated[FieldQuery, Query()], db: DB, actor: Editor):
    with api_errors():
        rows, total = result_service.list_fields(db, run_id, filters.page, filters.itemsPerPage,
                                                 filters.field_key, filters.review_status)
        return success(data=[ExtractedFieldResponse.model_validate(row) for row in rows],
                       meta=paginate(filters.page, filters.itemsPerPage, total))


def dispatch(db: Session, run, response: Response, *, explicit_retry: bool = False):
    if run.status == "completed":
        response.status_code = 200
        return success(data=RunResponse.model_validate(run), message="Extraction already completed")
    if run.status == "processing" and not explicit_retry:
        response.status_code = 202
        return success(data=RunResponse.model_validate(run), message="Extraction is processing", status_code=202)
    run = result_service.prepare_retry(db, run.id)
    # Another worker may have completed between the read and the retry lock.
    if run.status == "completed":
        response.status_code = 200
        return success(data=RunResponse.model_validate(run), message="Extraction already completed")
    queued = enqueue_field_extraction(run.id)
    if not queued:
        result_service.record_queue_failure(db, run.id)
    status = 202 if queued else 503
    response.status_code = status
    return success(data=RunResponse.model_validate(run), status_code=status,
                   message="Extraction queued" if queued else "Run saved; queue unavailable. Retry this run.")


@router.post("/document-versions/{version_id}/extraction-runs", response_model=ApiResponse[RunResponse], status_code=202)
def create_extraction_run(version_id: RecordId, payload: RunCreate, response: Response, db: DB, actor: Editor):
    with api_errors():
        run = result_service.create_run(db, version_id, request_key=f"manual:{payload.idempotency_key}", requested_by=actor.id)
        return dispatch(db, run, response)


@router.post("/extraction-runs/{run_id}/retry", response_model=ApiResponse[RunResponse], status_code=202)
def retry_extraction_run(run_id: RecordId, response: Response, db: DB, actor: Editor):
    with api_errors():
        return dispatch(db, result_service.get_run(db, run_id), response, explicit_retry=True)
