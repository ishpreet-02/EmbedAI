"""
Celery application setup.

Redis is used as the broker and result backend so FastAPI can enqueue slow
ingestion jobs and a separate worker process can run them.
"""

from celery import Celery

from config import REDIS_URL

celery_app = Celery(
    "embedai",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks.ingest"],
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)
