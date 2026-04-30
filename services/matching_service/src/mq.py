from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import aio_pika

from src.config import settings

_exchange: aio_pika.abc.AbstractExchange | None = None


async def connect() -> None:
    global _exchange
    try:
        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        channel = await connection.channel()
        _exchange = await channel.declare_exchange(
            "dating.events", aio_pika.ExchangeType.TOPIC, durable=True
        )
        print("MQ connected")
    except Exception as e:
        print(f"MQ connect failed: {e}")


async def publish(routing_key: str, payload: dict) -> None:
    if _exchange is None:
        return
    try:
        body = json.dumps(
            {
                "event_id": str(uuid.uuid4()),
                "event_type": routing_key,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": payload,
            }
        ).encode()
        await _exchange.publish(
            aio_pika.Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=routing_key,
        )
    except Exception as e:
        print(f"MQ publish error ({routing_key}): {e}")
