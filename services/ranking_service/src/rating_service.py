from __future__ import annotations

import time
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.calculator import calc_behavioral, calc_combined, calc_primary
from src.models import Rating, RatingHistory

_avg_likes_cache: tuple[float, float] | None = None
_AVG_LIKES_TTL = 60.0


async def get_or_create_rating(db: AsyncSession, user_id: uuid.UUID) -> Rating:
    rating = await db.scalar(select(Rating).where(Rating.user_id == user_id))
    if not rating:
        rating = Rating(user_id=user_id)
        db.add(rating)
        await db.flush()
    return rating


async def _avg_likes(db: AsyncSession) -> float:
    global _avg_likes_cache
    now = time.monotonic()
    if _avg_likes_cache and (now - _avg_likes_cache[1]) < _AVG_LIKES_TTL:
        return _avg_likes_cache[0]
    result = await db.scalar(
        text("SELECT AVG(total_likes_received) FROM ranking_schema.ratings")
    )
    val = float(result or 0)
    _avg_likes_cache = (val, now)
    return val


async def recalculate(db: AsyncSession, user_id: uuid.UUID) -> Rating:
    rating = await get_or_create_rating(db, user_id)

    # --- primary_score ---
    row = await db.execute(
        text("""
            SELECT
                p.completeness_score,
                COUNT(ph.id) AS photo_count,
                p.looking_for_gender,
                p.age_min,
                p.age_max
            FROM users_schema.profiles p
            LEFT JOIN users_schema.photos ph ON ph.profile_id = p.id
            WHERE p.user_id = :user_id
            GROUP BY p.completeness_score, p.looking_for_gender, p.age_min, p.age_max
        """),
        {"user_id": str(user_id)},
    )
    profile_row = row.fetchone()
    if profile_row:
        completeness = profile_row.completeness_score or 0
        photo_count = int(profile_row.photo_count or 0)
        prefs_filled = bool(
            profile_row.looking_for_gender != "any"
            or profile_row.age_min != 14
            or profile_row.age_max != -1
        )
        rating.primary_score = calc_primary(completeness, photo_count, prefs_filled)

    # --- behavioral_score ---
    avg_likes = await _avg_likes(db)
    rating.behavioral_score = calc_behavioral(
        total_likes=rating.total_likes_received,
        total_skips=rating.total_skips_received,
        total_matches=rating.total_matches,
        total_chats=rating.total_chats_initiated,
        avg_likes_system=avg_likes,
    )

    # --- combined_score ---
    referral_row = await db.scalar(
        text("SELECT COUNT(*) FROM ranking_schema.referrals WHERE referrer_id = :uid"),
        {"uid": str(user_id)},
    )
    referral_count = int(referral_row or 0)
    total_interactions = rating.total_likes_received + rating.total_skips_received
    rating.combined_score = calc_combined(
        rating.primary_score,
        rating.behavioral_score,
        total_interactions,
        referral_count,
    )

    db.add(
        RatingHistory(
            user_id=user_id,
            primary_score=rating.primary_score,
            behavioral_score=rating.behavioral_score,
            combined_score=rating.combined_score,
        )
    )

    await db.commit()
    await db.refresh(rating)
    return rating
