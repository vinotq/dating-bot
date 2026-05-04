from redis.asyncio import Redis

from config import settings
from user_client import UserClient
from ranking_client import RankingClient
from matching_client import MatchingClient
from notification_client import NotificationClient

user_client = UserClient()
ranking_client = RankingClient()
matching_client = MatchingClient()
notification_client = NotificationClient()
redis_client: Redis = Redis.from_url(settings.redis_dsn, decode_responses=True)


def _unread_key(user_id: str) -> str:
    return f"unread:{user_id}"


async def mark_unread(user_id: str, match_id: str) -> None:
    await redis_client.sadd(_unread_key(user_id), match_id)


async def clear_unread(user_id: str, match_id: str) -> None:
    await redis_client.srem(_unread_key(user_id), match_id)


async def get_unread_match_ids(user_id: str) -> set[str]:
    members = await redis_client.smembers(_unread_key(user_id))
    return set(members)
