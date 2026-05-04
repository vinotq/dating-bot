from __future__ import annotations

import asyncio
import logging
import uuid

from src.celery_app import celery

logger = logging.getLogger(__name__)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery.task(name="src.tasks.recalculate_all_ratings", bind=True, max_retries=3)
def recalculate_all_ratings(self):
    async def _inner():
        from sqlalchemy import select
        from src.db import SessionLocal
        from src.models import Rating
        from src.rating_service import recalculate

        async with SessionLocal() as db:
            user_ids = (
                await db.scalars(
                    select(Rating.user_id).order_by(Rating.updated_at.asc())
                )
            ).all()

        sem = asyncio.Semaphore(10)

        async def _one(uid):
            async with sem:
                async with SessionLocal() as db:
                    try:
                        await recalculate(db, uid)
                    except Exception:
                        logger.exception("recalculate failed: user_id=%s", uid)

        batch = 500
        for i in range(0, len(user_ids), batch):
            chunk = user_ids[i : i + batch]
            await asyncio.gather(*[_one(uid) for uid in chunk])

    try:
        _run(_inner())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@celery.task(name="src.tasks.recalculate_user_rating", bind=True, max_retries=3)
def recalculate_user_rating(self, user_id: str):
    async def _inner():
        from src.db import SessionLocal
        from src.rating_service import recalculate

        async with SessionLocal() as db:
            await recalculate(db, uuid.UUID(user_id))

    try:
        _run(_inner())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@celery.task(name="src.tasks.prefetch_feed", bind=True, max_retries=2)
def prefetch_feed(self, user_id: str):
    async def _inner():
        import httpx
        from redis.asyncio import Redis
        from src.config import settings
        from src.db import SessionLocal
        from src.feed import build_feed_from_db, get_shown, push_profile_ids

        redis = Redis.from_url(settings.redis_dsn, decode_responses=False)
        try:
            uid = uuid.UUID(user_id)
            swiped: list[str] = []
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(
                        f"{settings.matching_service_url}/api/v1/swipes/{uid}/swiped-ids"
                    )
                    if resp.status_code == 200:
                        swiped = resp.json()
            except Exception:
                pass

            async with SessionLocal() as db:
                shown = await get_shown(redis, uid)
                cards = await build_feed_from_db(
                    db,
                    uid,
                    limit=settings.feed_size,
                    exclude_profile_ids=shown,
                    exclude_user_ids=swiped,
                )
                if cards:
                    await push_profile_ids(
                        redis, uid, [str(c["profile_id"]) for c in cards]
                    )
        finally:
            await redis.aclose()

    try:
        _run(_inner())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=15)
