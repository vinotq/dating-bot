import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from config import settings
from dependencies import user_client
from handlers import router


async def main() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is empty")
    redis = Redis.from_url(settings.redis_dsn)
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=RedisStorage(redis=redis))
    dp.include_router(router)
    try:
        await dp.start_polling(bot)
    finally:
        await user_client.close()


if __name__ == "__main__":
    asyncio.run(main())
