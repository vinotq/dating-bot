import uuid

import httpx

from config import settings


class UserClient:
    def __init__(self) -> None:
        self.base_url = settings.user_service_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=20.0)

    async def close(self) -> None:
        await self.client.aclose()

    async def get_user(self, telegram_id: int) -> dict | None:
        response = await self.client.get(f"{self.base_url}/api/v1/users/{telegram_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    async def create_user(self, telegram_id: int, username: str | None) -> dict:
        response = await self.client.post(
            f"{self.base_url}/api/v1/users",
            json={"telegram_id": telegram_id, "username": username},
        )
        response.raise_for_status()
        return response.json()

    async def get_profile_by_user(self, user_id: str) -> dict | None:
        response = await self.client.get(f"{self.base_url}/api/v1/profiles/by-user/{user_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    async def create_profile(self, payload: dict) -> dict:
        response = await self.client.post(f"{self.base_url}/api/v1/profiles", json=payload)
        response.raise_for_status()
        return response.json()

    async def update_profile(self, profile_id: str, payload: dict) -> dict:
        response = await self.client.put(f"{self.base_url}/api/v1/profiles/{profile_id}", json=payload)
        response.raise_for_status()
        return response.json()

    async def delete_profile(self, profile_id: str) -> None:
        response = await self.client.delete(f"{self.base_url}/api/v1/profiles/{profile_id}")
        response.raise_for_status()

    async def list_interests(self) -> list[dict]:
        response = await self.client.get(f"{self.base_url}/api/v1/interests")
        response.raise_for_status()
        return response.json()

    async def create_interest(self, name: str) -> dict:
        response = await self.client.post(f"{self.base_url}/api/v1/interests", json={"name": name})
        response.raise_for_status()
        return response.json()

    async def set_user_interests(self, user_id: str, interest_ids: list[int]) -> None:
        response = await self.client.put(
            f"{self.base_url}/api/v1/users/{user_id}/interests",
            json={"interest_ids": interest_ids},
        )
        response.raise_for_status()

    async def upload_profile_photo(self, profile_id: str, content: bytes, filename: str) -> dict:
        files = {"file": (filename, content, "image/jpeg")}
        response = await self.client.post(
            f"{self.base_url}/api/v1/profiles/{profile_id}/photos",
            files=files,
        )
        response.raise_for_status()
        return response.json()

    async def list_profile_photos(self, profile_id: str) -> list[dict]:
        response = await self.client.get(f"{self.base_url}/api/v1/profiles/{profile_id}/photos")
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return response.json()

    async def fetch_photo_bytes(self, profile_id: str, photo_id: str) -> bytes:
        response = await self.client.get(
            f"{self.base_url}/api/v1/profiles/{profile_id}/photos/{photo_id}/file",
        )
        response.raise_for_status()
        return response.content

    async def delete_profile_photo(self, profile_id: str, photo_id: str) -> None:
        response = await self.client.delete(
            f"{self.base_url}/api/v1/profiles/{profile_id}/photos/{photo_id}",
        )
        response.raise_for_status()

    async def reorder_profile_photos(self, profile_id: str, photo_ids: list[str]) -> list[dict]:
        response = await self.client.put(
            f"{self.base_url}/api/v1/profiles/{profile_id}/photos/order",
            json={"photo_ids": photo_ids},
        )
        response.raise_for_status()
        return response.json()

    async def get_preferences(self, user_id: str) -> dict:
        response = await self.client.get(f"{self.base_url}/api/v1/users/{user_id}/preferences")
        response.raise_for_status()
        return response.json()

    async def update_preferences(self, user_id: str, looking_for_gender: str, age_min: int, age_max: int) -> dict:
        response = await self.client.put(
            f"{self.base_url}/api/v1/users/{user_id}/preferences",
            json={
                "looking_for_gender": looking_for_gender,
                "age_min": age_min,
                "age_max": age_max,
            },
        )
        response.raise_for_status()
        return response.json()


def parse_uuid(value: str) -> str:
    return str(uuid.UUID(value))
