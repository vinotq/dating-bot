import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand
from redis.asyncio import Redis

from config import settings
from dependencies import matching_client, ranking_client, user_client
from handlers import router
from mq_consumer import start_match_consumer


BOT_COMMANDS = [
    BotCommand(command="start", description="Запуск и регистрация"),
    BotCommand(command="search", description="Смотреть анкеты"),
    BotCommand(command="matches", description="Мои мэтчи"),
    BotCommand(command="profile", description="Мой профиль"),
    BotCommand(command="settings", description="Настройки"),
    BotCommand(command="help", description="Помощь"),
]


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
    await bot.set_my_commands(BOT_COMMANDS)
    consumer_task = asyncio.create_task(start_match_consumer(bot))
    try:
        await dp.start_polling(bot)
    finally:
        consumer_task.cancel()
        await user_client.close()
        await ranking_client.close()
        await matching_client.close()


if __name__ == "__main__":
    asyncio.run(main())
