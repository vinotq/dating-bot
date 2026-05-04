from __future__ import annotations

import json
import logging

import aio_pika
from aiogram import Bot
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from config import settings

logger = logging.getLogger(__name__)


async def _get_telegram_id(user_uuid: str) -> int | None:
    from dependencies import user_client
    try:
        resp = await user_client.client.get(
            f"{user_client.base_url}/api/v1/users/by-uuid/{user_uuid}"
        )
        if resp.status_code != 200:
            return None
        return resp.json()["telegram_id"]
    except Exception:
        logger.exception("_get_telegram_id failed: user_uuid=%s", user_uuid)
        return None


async def start_match_consumer(bot: Bot) -> None:
    bot_me = await bot.get_me()
    try:
        redis = Redis.from_url(settings.redis_dsn)
        storage = RedisStorage(redis=redis)

        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=5)

        exchange = await channel.declare_exchange(
            "dating.events", aio_pika.ExchangeType.TOPIC, durable=True
        )
        queue = await channel.declare_queue("bot.notifications", durable=True)
        await queue.bind(exchange, routing_key="message.sent")
        await queue.bind(exchange, routing_key="notify.outbound")

        async with queue.iterator() as it:
            async for message in it:
                async with message.process():
                    routing_key = ""
                    try:
                        envelope = json.loads(message.body)
                        routing_key = envelope.get("event_type", "")
                        payload = envelope["payload"]
                        if routing_key == "message.sent":
                            await _deliver_message(bot, storage, bot_me.id, payload)
                        elif routing_key == "notify.outbound":
                            await _notify_outbound(bot, payload)
                    except Exception:
                        logger.exception("Consumer error: event_type=%s", routing_key)

    except Exception:
        logger.exception("Consumer start error")


async def _notify_outbound(bot: Bot, payload: dict) -> None:
    user_uuid = payload.get("user_id")
    notif_type = payload.get("type")
    notif_payload = payload.get("payload", {})

    if not user_uuid:
        return

    tg_id = await _get_telegram_id(user_uuid)
    if tg_id is None:
        return

    if notif_type == "match":
        text = "<b>У тебя мэтч!</b> Открой «Мои мэтчи», чтобы написать ❤️"
    elif notif_type == "like":
        text = "<b>Кто-то поставил тебе лайк!</b> Продолжай свайпить — вдруг мэтч 🔥"
    elif notif_type == "digest":
        new_likes = int(notif_payload.get("new_likes") or 0)
        new_matches = int(notif_payload.get("new_matches") or 0)
        parts = []
        if new_likes:
            parts.append(f"<b>{new_likes}</b> новых лайков")
        if new_matches:
            parts.append(f"<b>{new_matches}</b> новых мэтчей")
        if not parts:
            return
        text = "За последние сутки: " + ", ".join(parts) + "."
    elif notif_type == "referral":
        text = "<b>Твой друг зарегистрировался по реферальной ссылке!</b> Бонус уже добавлен к рейтингу 🎉"
    else:
        return

    try:
        await bot.send_message(chat_id=tg_id, text=text, parse_mode="HTML")
    except Exception:
        logger.exception("notify_outbound send error: user=%s type=%s", user_uuid, notif_type)


async def _deliver_message(bot: Bot, storage: RedisStorage, bot_id: int, payload: dict) -> None:
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.base import StorageKey
    from states import ChatState

    receiver_uuid = payload.get("receiver_id")
    match_id = payload.get("match_id")
    body = payload.get("body", "")

    if not receiver_uuid or not match_id:
        return

    tg_id = await _get_telegram_id(receiver_uuid)
    if tg_id is None:
        return

    try:
        key = StorageKey(bot_id=bot_id, chat_id=tg_id, user_id=tg_id)
        ctx = FSMContext(storage=storage, key=key)
        state = await ctx.get_state()
        data = await ctx.get_data()

        if state == ChatState.active.state and str(data.get("match_id")) == str(match_id):
            import html as _html
            partner_name = _html.escape(data.get("partner_name") or "Партнёр")
            await bot.send_message(
                chat_id=tg_id,
                text=f"<b>{partner_name}:</b> {_html.escape(body[:200])}",
                parse_mode="HTML",
            )
        else:
            from dependencies import mark_unread
            await mark_unread(str(receiver_uuid), str(match_id))
            await bot.send_message(
                chat_id=tg_id,
                text="<b>Новое сообщение</b> — открой мэтч, чтобы прочитать.",
                parse_mode="HTML",
            )
    except Exception:
        logger.exception("Deliver message error: receiver=%s", receiver_uuid)
