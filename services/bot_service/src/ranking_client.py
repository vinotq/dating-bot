import uuid

import httpx

from config import settings


class RankingClient:
    def __init__(self) -> None:
        self.base_url = settings.ranking_service_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=20.0)

    async def close(self) -> None:
        await self.client.aclose()

    async def get_feed(self, user_id: str) -> dict | None:
        response = await self.client.get(f"{self.base_url}/api/v1/feed/{user_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    async def reset_feed(self, user_id: str) -> None:
        response = await self.client.delete(f"{self.base_url}/api/v1/feed/{user_id}")
        response.raise_for_status()
