from __future__ import annotations

import httpx

from config import settings


class NotificationClient:
    def __init__(self) -> None:
        self.base_url = settings.notification_service_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        await self.client.aclose()

    async def get_settings(self, user_id: str) -> dict:
        resp = await self.client.get(
            f"{self.base_url}/api/v1/notifications/{user_id}/settings"
        )
        resp.raise_for_status()
        return resp.json()

    async def update_settings(
        self,
        user_id: str,
        matches_enabled: bool,
        messages_enabled: bool,
        digest_enabled: bool,
    ) -> dict:
        resp = await self.client.put(
            f"{self.base_url}/api/v1/notifications/{user_id}/settings",
            params={
                "matches_enabled": matches_enabled,
                "messages_enabled": messages_enabled,
                "digest_enabled": digest_enabled,
            },
        )
        resp.raise_for_status()
        return resp.json()
