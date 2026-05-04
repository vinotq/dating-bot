from __future__ import annotations

import json
import logging
import uuid

import aio_pika
from sqlalchemy import select, text

from src.config import settings
from src.db import SessionLocal
from src.models import Rating
from src.rating_service import get_or_create_rating, recalculate

logger = logging.getLogger(__name__)


async def _handle(routing_key: str, payload: dict) -> None:
    async with SessionLocal() as db:
        try:
            if routing_key == "user.registered":
                user_id = uuid.UUID(payload["user_id"])
                await get_or_create_rating(db, user_id)
                await db.commit()

            elif routing_key in ("profile.created", "profile.updated", "photo.uploaded"):
                user_id = uuid.UUID(payload["user_id"])
                await recalculate(db, user_id)

            elif routing_key == "swipe.created":
                swiped_id = uuid.UUID(payload["swiped_id"])
                action = payload.get("action", "skip")
                rating = await get_or_create_rating(db, swiped_id)
                if action == "like":
                    rating.total_likes_received += 1
                else:
                    rating.total_skips_received += 1
                await db.flush()
                await recalculate(db, swiped_id)

            elif routing_key == "match.created":
                for key in ("user1_id", "user2_id"):
                    uid = uuid.UUID(payload[key])
                    rating = await get_or_create_rating(db, uid)
                    rating.total_matches += 1
                    await db.flush()
                    await recalculate(db, uid)

            elif routing_key == "message.sent":
                if payload.get("is_first_message"):
                    sender_id = uuid.UUID(payload["sender_id"])
                    rating = await get_or_create_rating(db, sender_id)
                    rating.total_chats_initiated += 1
                    await db.flush()
                    await recalculate(db, sender_id)

            elif routing_key == "referral.created":
                referrer_id = uuid.UUID(payload["referrer_id"])
                referred_id = uuid.UUID(payload["referred_id"])
                await db.execute(
                    text("""
                        INSERT INTO ranking_schema.referrals (id, referrer_id, referred_id)
                        VALUES (gen_random_uuid(), :referrer_id, :referred_id)
                        ON CONFLICT DO NOTHING
                    """),
                    {"referrer_id": str(referrer_id), "referred_id": str(referred_id)},
                )
                await db.flush()
                await recalculate(db, referrer_id)

        except Exception:
            logger.exception("Consumer error: routing_key=%s", routing_key)
            await db.rollback()


async def start_consumer() -> None:
    try:
        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)

        exchange = await channel.declare_exchange(
            "dating.events", aio_pika.ExchangeType.TOPIC, durable=True
        )
        queue = await channel.declare_queue("ranking.events", durable=True)

        for key in (
            "user.registered",
            "profile.created",
            "profile.updated",
            "photo.uploaded",
            "swipe.created",
            "match.created",
            "message.sent",
            "referral.created",
        ):
            await queue.bind(exchange, routing_key=key)

        async with queue.iterator() as it:
            async for message in it:
                async with message.process():
                    try:
                        envelope = json.loads(message.body)
                        await _handle(envelope["event_type"], envelope["payload"])
                    except Exception:
                        logger.exception("Consumer parse error")

    except Exception:
        logger.exception("Consumer start error")
