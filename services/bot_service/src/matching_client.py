import httpx

from config import settings


class MatchingClient:
    def __init__(self) -> None:
        self.base_url = settings.matching_service_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=20.0)

    async def close(self) -> None:
        await self.client.aclose()

    async def swipe(self, swiper_id: str, swiped_id: str, action: str) -> dict:
        response = await self.client.post(
            f"{self.base_url}/api/v1/swipes",
            json={"swiper_id": swiper_id, "swiped_id": swiped_id, "action": action},
        )
        response.raise_for_status()
        return response.json()

    async def get_matches(self, user_id: str) -> list[dict]:
        response = await self.client.get(f"{self.base_url}/api/v1/matches/{user_id}")
        response.raise_for_status()
        return response.json()

    async def send_message(self, match_id: str, sender_id: str, body: str) -> dict:
        response = await self.client.post(
            f"{self.base_url}/api/v1/messages",
            json={"match_id": match_id, "sender_id": sender_id, "body": body},
        )
        response.raise_for_status()
        return response.json()

    async def get_messages(self, match_id: str) -> list[dict]:
        response = await self.client.get(f"{self.base_url}/api/v1/messages/{match_id}")
        response.raise_for_status()
        return response.json()
