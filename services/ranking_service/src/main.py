import asyncio
import logging
import uuid

import httpx
from fastapi import Depends, FastAPI, HTTPException, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette_prometheus import PrometheusMiddleware
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src import consumer as mq_consumer
from src.config import settings
from src.db import get_db
from src.feed import (
    build_feed_from_db,
    get_profile_card,
    get_shown,
    mark_shown,
    pop_next_profile_id,
    push_profile_ids,
    queue_length,
)
from src.models import Rating
from src.rating_service import recalculate
from src.schemas import FeedCard, RatingOut

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","service":"ranking_service","level":"%(levelname)s","msg":"%(message)s"}',
)

app = FastAPI(title="Ranking Service", version="0.1.0")
app.add_middleware(PrometheusMiddleware)

_redis: Redis | None = None
_matching_client: httpx.AsyncClient | None = None


def get_matching_client() -> httpx.AsyncClient:
    assert _matching_client is not None
    return _matching_client


async def _fetch_swiped_ids(user_id: uuid.UUID) -> list[str]:
    try:
        resp = await get_matching_client().get(
            f"{settings.matching_service_url}/api/v1/swipes/{user_id}/swiped-ids"
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return []


feed_cache_hits = Counter("feed_cache_hits_total", "Feed served from Redis cache")
feed_cache_misses = Counter("feed_cache_misses_total", "Feed required DB query")
feed_duration = Histogram("feed_get_duration_seconds", "Time to build feed response")
rating_recalc_duration = Histogram(
    "rating_recalculation_duration_seconds", "Rating recalc time"
)


def get_redis() -> Redis:
    assert _redis is not None
    return _redis


@app.on_event("startup")
async def startup() -> None:
    global _redis, _matching_client
    _redis = Redis.from_url(settings.redis_dsn, decode_responses=False)
    _matching_client = httpx.AsyncClient(timeout=5.0)
    asyncio.create_task(mq_consumer.start_consumer())


@app.on_event("shutdown")
async def shutdown() -> None:
    if _redis:
        await _redis.aclose()
    if _matching_client:
        await _matching_client.aclose()


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(select(1))
    assert _redis is not None
    await _redis.ping()
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/v1/feed/{user_id}", response_model=FeedCard)
async def get_feed(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> FeedCard:
    with feed_duration.time():
        n = await queue_length(redis, user_id)

        if n == 0:
            feed_cache_misses.inc()
            shown = await get_shown(redis, user_id)
            swiped = await _fetch_swiped_ids(user_id)
            cards = await build_feed_from_db(
                db,
                user_id,
                limit=settings.feed_size,
                exclude_profile_ids=shown,
                exclude_user_ids=swiped,
            )
            if not cards:
                raise HTTPException(status_code=404, detail="Больше анкет нет")
            await push_profile_ids(
                redis, user_id, [str(c["profile_id"]) for c in cards]
            )
        else:
            feed_cache_hits.inc()

        card = None
        for _ in range(settings.feed_size + 1):
            raw = await pop_next_profile_id(redis, user_id)
            if not raw:
                break
            candidate = await get_profile_card(db, uuid.UUID(raw))
            if not candidate:
                continue
            if str(candidate["user_id"]) == str(user_id):
                continue
            card = candidate
            break

        if not card:
            shown = await get_shown(redis, user_id)
            swiped = await _fetch_swiped_ids(user_id)
            cards = await build_feed_from_db(
                db,
                user_id,
                limit=settings.feed_size,
                exclude_profile_ids=shown,
                exclude_user_ids=swiped,
            )
            if not cards:
                raise HTTPException(status_code=404, detail="Больше анкет нет")
            await push_profile_ids(
                redis, user_id, [str(c["profile_id"]) for c in cards]
            )
            raw = await pop_next_profile_id(redis, user_id)
            if not raw:
                raise HTTPException(status_code=404, detail="Больше анкет нет")
            card = await get_profile_card(db, uuid.UUID(raw))
            if not card:
                raise HTTPException(status_code=404, detail="Анкета не найдена")

        await mark_shown(redis, user_id, str(card["profile_id"]))

        remaining = await queue_length(redis, user_id)
        if remaining <= 1:
            from src.tasks import prefetch_feed

            prefetch_feed.delay(str(user_id))

        return FeedCard(
            profile_id=card["profile_id"],
            user_id=card["user_id"],
            name=card["name"],
            age=card["age"],
            city=card["city"],
            bio=card.get("bio"),
            gender=card["gender"],
            looking_for_gender=card["looking_for_gender"],
            primary_photo_id=card.get("primary_photo_id"),
            combined_score=float(card.get("combined_score") or 0),
            interests=list(card.get("interests") or []),
        )


@app.delete("/api/v1/feed/{user_id}", status_code=204)
async def reset_feed(
    user_id: uuid.UUID,
    redis: Redis = Depends(get_redis),
) -> None:
    from src.feed import _feed_key, _shown_key

    await redis.delete(_feed_key(user_id), _shown_key(user_id))


@app.get("/api/v1/ratings/{user_id}", response_model=RatingOut)
async def get_rating(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Rating:
    rating = await db.scalar(select(Rating).where(Rating.user_id == user_id))
    if not rating:
        raise HTTPException(status_code=404, detail="Рейтинг не найден")
    return rating


@app.post("/api/v1/ratings/{user_id}/recalculate", response_model=RatingOut)
async def force_recalculate(
    user_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Rating:
    with rating_recalc_duration.time():
        return await recalculate(db, user_id)
