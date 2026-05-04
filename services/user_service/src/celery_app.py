from __future__ import annotations

from celery import Celery

from src.config import settings

celery = Celery(
    "user_service",
    broker=settings.redis_dsn,
    backend=settings.redis_dsn,
    include=["src.tasks"],
)
celery.conf.task_serializer = "json"
celery.conf.result_serializer = "json"
celery.conf.accept_content = ["json"]
