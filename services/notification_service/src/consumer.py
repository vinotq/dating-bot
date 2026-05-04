from __future__ import annotations

import json
import logging

import aio_pika
from redis.asyncio import Redis

from src.config import settings
from src.tasks import send_notification

logger = logging.getLogger(__name__)

LIKE_NOTIF_TTL = 3600


async def _handle(routing_key: str, payload: dict, redis: Redis) -> None:
    if routing_key == "match.created":
        for key in ("user1_id", "user2_id"):
            uid = payload.get(key)
            if uid:
                send_notification.delay(
                    uid,
                    "match",
                    {
                        "match_id": payload.get("match_id"),
                        "partner_id": payload.get(
                            "user2_id" if key == "user1_id" else "user1_id"
                        ),
                    },
                )

    elif routing_key == "referral.created":
        referrer_id = payload.get("referrer_id")
        if referrer_id:
            send_notification.delay(
                referrer_id,
                "referral",
                {
                    "referred_id": payload.get("referred_id"),
                },
            )

    elif routing_key == "swipe.created" and payload.get("action") == "like":
        swiped_id = payload.get("swiped_id")
        if swiped_id:
            rate_key = f"like_notif:{swiped_id}"
            if not await redis.exists(rate_key):
                await redis.setex(rate_key, LIKE_NOTIF_TTL, "1")
                send_notification.delay(
                    swiped_id,
                    "like",
                    {
                        "from_user_id": payload.get("swiper_id"),
                    },
                )


async def start_consumer() -> None:
    redis = Redis.from_url(settings.redis_dsn)
    try:
        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)

        exchange = await channel.declare_exchange(
            "dating.events", aio_pika.ExchangeType.TOPIC, durable=True
        )
        queue = await channel.declare_queue("notification.events", durable=True)

        for key in ("match.created", "swipe.created", "referral.created"):
            await queue.bind(exchange, routing_key=key)

        async with queue.iterator() as it:
            async for message in it:
                async with message.process():
                    try:
                        envelope = json.loads(message.body)
                        event_type = envelope["event_type"]
                        await _handle(event_type, envelope["payload"], redis)
                    except Exception:
                        logger.exception("Consumer error")

    except Exception:
        logger.exception("Consumer start error")
    finally:
        await redis.aclose()
