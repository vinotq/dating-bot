from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import aio_pika

from src.config import settings

_channel: aio_pika.abc.AbstractChannel | None = None
_exchange: aio_pika.abc.AbstractExchange | None = None


async def connect() -> None:
    global _channel, _exchange
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    _channel = await connection.channel()
    _exchange = await _channel.declare_exchange(
        "dating.events", aio_pika.ExchangeType.TOPIC, durable=True
    )


async def publish(routing_key: str, payload: dict) -> None:
    assert _exchange is not None
    body = json.dumps({
        "event_id": str(uuid.uuid4()),
        "event_type": routing_key,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }).encode()
    await _exchange.publish(
        aio_pika.Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
        routing_key=routing_key,
    )


async def publish_one(routing_key: str, payload: dict) -> None:
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    try:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            "dating.events", aio_pika.ExchangeType.TOPIC, durable=True
        )
        body = json.dumps({
            "event_id": str(uuid.uuid4()),
            "event_type": routing_key,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }).encode()
        await exchange.publish(
            aio_pika.Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=routing_key,
        )
    finally:
        await connection.close()
