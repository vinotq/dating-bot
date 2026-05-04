from celery import Celery
from src.config import settings

celery = Celery(
    "notifications",
    broker=settings.rabbitmq_url,
    backend=settings.redis_dsn.replace("/0", "/2"),
    include=["src.tasks"],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "daily-digest": {
            "task": "src.tasks.daily_digest",
            "schedule": 86400,
        },
    },
)
