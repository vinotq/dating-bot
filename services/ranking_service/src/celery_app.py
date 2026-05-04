from celery import Celery
from src.config import settings

celery = Celery(
    "ranking",
    broker=settings.rabbitmq_url.replace("amqp://", "amqp://").replace("amqps://", "amqps://"),
    backend=settings.redis_dsn.replace("/0", "/1"),
    include=["src.tasks"],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "recalculate-all-ratings": {
            "task": "src.tasks.recalculate_all_ratings",
            "schedule": 6 * 3600,
        },
    },
)
