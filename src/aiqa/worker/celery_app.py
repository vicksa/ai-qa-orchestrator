from celery import Celery

from aiqa.config import settings

celery_app = Celery("aiqa", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_always_eager=settings.celery_task_always_eager,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
)
celery_app.autodiscover_tasks(["aiqa.worker"])
