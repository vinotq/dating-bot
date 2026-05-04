from __future__ import annotations

import uuid

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings


def _feed_key(user_id: uuid.UUID) -> str:
    return f"feed:{user_id}"


def _shown_key(user_id: uuid.UUID) -> str:
    return f"feed_shown:{user_id}"


async def pop_next_profile_id(redis: Redis, user_id: uuid.UUID) -> str | None:
    key = _feed_key(user_id)
    value = await redis.lpop(key)
    if value is None:
        return None
    return value.decode() if isinstance(value, bytes) else value


async def queue_length(redis: Redis, user_id: uuid.UUID) -> int:
    return await redis.llen(_feed_key(user_id))


async def mark_shown(redis: Redis, user_id: uuid.UUID, profile_id: str) -> None:
    key = _shown_key(user_id)
    await redis.sadd(key, profile_id)
    await redis.expire(key, settings.feed_ttl)


async def get_shown(redis: Redis, user_id: uuid.UUID) -> set[str]:
    key = _shown_key(user_id)
    raw = await redis.smembers(key)
    return {v.decode() if isinstance(v, bytes) else v for v in raw}


async def push_profile_ids(
    redis: Redis, user_id: uuid.UUID, profile_ids: list[str]
) -> None:
    if not profile_ids:
        return
    key = _feed_key(user_id)
    existing_raw = await redis.lrange(key, 0, -1)
    existing = {v.decode() if isinstance(v, bytes) else v for v in existing_raw}
    shown = await get_shown(redis, user_id)
    fresh = [pid for pid in profile_ids if pid not in existing and pid not in shown]
    if not fresh:
        return
    await redis.rpush(key, *fresh)
    await redis.expire(key, settings.feed_ttl)


async def build_feed_from_db(
    db: AsyncSession,
    requester_user_id: uuid.UUID,
    limit: int = 10,
    exclude_profile_ids: set[str] | None = None,
    exclude_user_ids: list[str] | None = None,
) -> list[dict]:
    swiped = exclude_user_ids or []
    rows = await db.execute(
        text("""
            SELECT
                p.id          AS profile_id,
                u.id          AS user_id,
                p.name,
                p.age,
                p.city,
                p.bio,
                p.gender,
                p.looking_for_gender,
                ph.id         AS primary_photo_id,
                COALESCE(r.combined_score, 0) AS combined_score,
                COALESCE(
                    (SELECT array_agg(i.name ORDER BY i.name)
                     FROM users_schema.user_interests ui
                     JOIN users_schema.interests i ON i.id = ui.interest_id
                     WHERE ui.user_id = p.user_id),
                    '{}'::text[]
                ) AS interests
            FROM users_schema.profiles p
            JOIN users_schema.users u ON u.id = p.user_id AND u.is_active = true
            LEFT JOIN ranking_schema.ratings r ON r.user_id = p.user_id
            LEFT JOIN LATERAL (
                SELECT id
                FROM users_schema.photos
                WHERE profile_id = p.id
                ORDER BY is_primary DESC, display_order ASC
                LIMIT 1
            ) ph ON true
            WHERE p.user_id <> :requester_user_id
              AND (:exclude_count = 0 OR p.id <> ALL(CAST(:exclude_ids AS uuid[])))
              AND (:swiped_count = 0 OR p.user_id <> ALL(CAST(:swiped_ids AS uuid[])))
              AND (
                  SELECT looking_for_gender FROM users_schema.profiles
                  WHERE user_id = :requester_user_id
              ) IN ('any', p.gender)
              AND p.age >= (
                  SELECT age_min FROM users_schema.profiles
                  WHERE user_id = :requester_user_id
              )
              AND (
                  (SELECT age_max FROM users_schema.profiles WHERE user_id = :requester_user_id) = -1
                  OR p.age <= (SELECT age_max FROM users_schema.profiles WHERE user_id = :requester_user_id)
              )
            ORDER BY combined_score DESC
            LIMIT :limit
        """),
        {
            "requester_user_id": str(requester_user_id),
            "limit": limit,
            "exclude_ids": list(exclude_profile_ids or []),
            "exclude_count": len(exclude_profile_ids or []),
            "swiped_ids": swiped,
            "swiped_count": len(swiped),
        },
    )
    return [dict(row._mapping) for row in rows]


async def get_profile_card(db: AsyncSession, profile_id: uuid.UUID) -> dict | None:
    row = await db.execute(
        text("""
            SELECT
                p.id          AS profile_id,
                u.id          AS user_id,
                p.name,
                p.age,
                p.city,
                p.bio,
                p.gender,
                p.looking_for_gender,
                ph.id         AS primary_photo_id,
                COALESCE(r.combined_score, 0) AS combined_score,
                COALESCE(
                    (SELECT array_agg(i.name ORDER BY i.name)
                     FROM users_schema.user_interests ui
                     JOIN users_schema.interests i ON i.id = ui.interest_id
                     WHERE ui.user_id = p.user_id),
                    '{}'::text[]
                ) AS interests
            FROM users_schema.profiles p
            JOIN users_schema.users u ON u.id = p.user_id
            LEFT JOIN ranking_schema.ratings r ON r.user_id = p.user_id
            LEFT JOIN LATERAL (
                SELECT id
                FROM users_schema.photos
                WHERE profile_id = p.id
                ORDER BY is_primary DESC, display_order ASC
                LIMIT 1
            ) ph ON true
            WHERE p.id = :profile_id
        """),
        {"profile_id": str(profile_id)},
    )
    r = row.fetchone()
    return dict(r._mapping) if r else None
