from __future__ import annotations

import json
import uuid

import aio_pika
from sqlalchemy import select, text

from src.config import settings
from src.db import SessionLocal
from src.models import Rating
from src.rating_service import get_or_create_rating, recalculate


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

        except Exception as e:
            print(f"Consumer error [{routing_key}]: {e}")
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
        ):
            await queue.bind(exchange, routing_key=key)

        async with queue.iterator() as it:
            async for message in it:
                async with message.process():
                    try:
                        envelope = json.loads(message.body)
                        await _handle(envelope["event_type"], envelope["payload"])
                    except Exception as e:
                        print(f"Consumer parse error: {e}")

    except Exception as e:
        print(f"Consumer start error: {e}")
