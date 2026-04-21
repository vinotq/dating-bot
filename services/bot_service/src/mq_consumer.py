from __future__ import annotations

import json

import aio_pika
from aiogram import Bot

from config import settings


async def start_match_consumer(bot: Bot) -> None:
    try:
        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=5)

        exchange = await channel.declare_exchange(
            "dating.events", aio_pika.ExchangeType.TOPIC, durable=True
        )
        queue = await channel.declare_queue("bot.match.notifications", durable=True)
        await queue.bind(exchange, routing_key="match.created")

        async with queue.iterator() as it:
            async for message in it:
                async with message.process():
                    try:
                        envelope = json.loads(message.body)
                        payload = envelope["payload"]
                        await _notify_match(bot, payload)
                    except Exception as e:
                        print(f"Match consumer error: {e}")

    except Exception as e:
        print(f"Match consumer start error: {e}")


async def _notify_match(bot: Bot, payload: dict) -> None:
    from dependencies import user_client

    for key in ("user1_id", "user2_id"):
        user_id = payload.get(key)
        if not user_id:
            continue
        try:
            # Ищем telegram_id через user_service
            from sqlalchemy import select, text
            # user_service не даёт GET по UUID напрямую — используем GET /users/{telegram_id}
            # Вместо этого делаем запрос к user_service через внутренний эндпоинт by UUID
            resp = await user_client.client.get(
                f"{user_client.base_url}/api/v1/users/by-uuid/{user_id}"
            )
            if resp.status_code != 200:
                continue
            user_data = resp.json()
            telegram_id = user_data["telegram_id"]
            await bot.send_message(
                chat_id=telegram_id,
                text="<b>У тебя мэтч!</b> Загляни в раздел /matches",
                parse_mode="HTML",
            )
        except Exception as e:
            print(f"Match notify error for {user_id}: {e}")
