from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from src.celery_app import celery

logger = logging.getLogger(__name__)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery.task(name="src.tasks.send_notification", bind=True, max_retries=3)
def send_notification(self, user_id: str, notif_type: str, payload: dict) -> None:
    async def _inner():
        from sqlalchemy import select
        from src.db import SessionLocal
        from src.models import Notification, NotificationSettings
        from src import mq

        uid = uuid.UUID(user_id)
        async with SessionLocal() as db:
            settings_row = await db.scalar(
                select(NotificationSettings).where(NotificationSettings.user_id == uid)
            )
            if settings_row:
                if notif_type == "match" and not settings_row.matches_enabled:
                    return
                if notif_type == "message" and not settings_row.messages_enabled:
                    return

            notif = Notification(user_id=uid, type=notif_type, payload=payload, status="pending")
            db.add(notif)
            await db.commit()
            await db.refresh(notif)

            try:
                await mq.publish_one("notify.outbound", {
                    "user_id": user_id,
                    "type": notif_type,
                    "payload": payload,
                    "notification_id": str(notif.id),
                })
                notif.status = "sent"
            except Exception:
                notif.status = "failed"
                raise
            finally:
                await db.commit()

    try:
        _run(_inner())
    except Exception as exc:
        logger.exception("send_notification failed: user_id=%s type=%s", user_id, notif_type)
        raise self.retry(exc=exc, countdown=30)


@celery.task(name="src.tasks.daily_digest")
def daily_digest() -> None:
    async def _inner():
        import httpx
        from sqlalchemy import select
        from src.config import settings
        from src.db import SessionLocal
        from src.models import NotificationSettings
        from src import mq

        since = datetime.now(timezone.utc) - timedelta(days=1)
        since_iso = since.isoformat()

        async with SessionLocal() as db:
            enabled = (await db.scalars(
                select(NotificationSettings).where(NotificationSettings.digest_enabled == True)
            )).all()

            async with httpx.AsyncClient(timeout=10.0) as http:
                for s in enabled:
                    uid = str(s.user_id)
                    try:
                        resp = await http.get(
                            f"{settings.matching_service_url}/api/v1/swipes/{uid}/stats",
                            params={"since": since_iso},
                        )
                        resp.raise_for_status()
                        stats = resp.json()
                    except Exception:
                        logger.exception("digest: failed to fetch stats for user_id=%s", uid)
                        continue

                    new_likes = int(stats.get("new_likes", 0))
                    new_matches = int(stats.get("new_matches", 0))

                    if new_likes == 0 and new_matches == 0:
                        continue

                    await mq.publish_one("notify.outbound", {
                        "user_id": uid,
                        "type": "digest",
                        "payload": {"new_likes": new_likes, "new_matches": new_matches},
                    })

    _run(_inner())
