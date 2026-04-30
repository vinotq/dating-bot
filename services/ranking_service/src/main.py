import asyncio
import uuid

from fastapi import Depends, FastAPI, HTTPException
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
from src.rating_service import get_or_create_rating, recalculate
from src.schemas import FeedCard, RatingOut

app = FastAPI(title="Ranking Service", version="0.1.0")

_redis: Redis | None = None


def get_redis() -> Redis:
    assert _redis is not None
    return _redis


@app.on_event("startup")
async def startup() -> None:
    global _redis
    _redis = Redis.from_url(settings.redis_dsn, decode_responses=False)
    asyncio.create_task(mq_consumer.start_consumer())


@app.on_event("shutdown")
async def shutdown() -> None:
    if _redis:
        await _redis.aclose()


@app.get("/api/v1/feed/{user_id}", response_model=FeedCard)
async def get_feed(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> FeedCard:
    n = await queue_length(redis, user_id)

    if n == 0:
        shown = await get_shown(redis, user_id)
        cards = await build_feed_from_db(
            db, user_id, limit=settings.feed_size, exclude_profile_ids=shown
        )
        if not cards:
            raise HTTPException(status_code=404, detail="Больше анкет нет")
        await push_profile_ids(redis, user_id, [str(c["profile_id"]) for c in cards])

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
        cards = await build_feed_from_db(
            db, user_id, limit=settings.feed_size, exclude_profile_ids=shown
        )
        if not cards:
            raise HTTPException(status_code=404, detail="Больше анкет нет")
        await push_profile_ids(redis, user_id, [str(c["profile_id"]) for c in cards])
        raw = await pop_next_profile_id(redis, user_id)
        if not raw:
            raise HTTPException(status_code=404, detail="Больше анкет нет")
        card = await get_profile_card(db, uuid.UUID(raw))
        if not card:
            raise HTTPException(status_code=404, detail="Анкета не найдена")

    await mark_shown(redis, user_id, str(card["profile_id"]))

    remaining = await queue_length(redis, user_id)
    if remaining <= 1:
        asyncio.create_task(_prefetch(redis, user_id))

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


async def _prefetch(redis: Redis, user_id: uuid.UUID) -> None:
    try:
        from src.db import SessionLocal
        async with SessionLocal() as fresh_db:
            shown = await get_shown(redis, user_id)
            cards = await build_feed_from_db(
                fresh_db, user_id, limit=settings.feed_size, exclude_profile_ids=shown
            )
            if cards:
                await push_profile_ids(redis, user_id, [str(c["profile_id"]) for c in cards])
    except Exception as e:
        print(f"Prefetch error: {e}")


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
async def force_recalculate(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Rating:
    return await recalculate(db, user_id)
