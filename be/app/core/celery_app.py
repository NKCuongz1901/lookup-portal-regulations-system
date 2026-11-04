from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "lookup_portal",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.modules.extractions.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
)

# Register task modules on import (workers also load via ``include``).
from app.modules.extractions import tasks as _extraction_tasks  # noqa: E402, F401