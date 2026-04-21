import uuid

from pydantic import BaseModel


class FeedCard(BaseModel):
    profile_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    age: int
    city: str
    bio: str | None
    gender: str
    looking_for_gender: str
    primary_photo_id: uuid.UUID | None
    combined_score: float = 0.0
    interests: list[str] = []


class RatingOut(BaseModel):
    user_id: uuid.UUID
    primary_score: float
    behavioral_score: float
    combined_score: float
    total_likes_received: int
    total_skips_received: int
    total_matches: int

    model_config = {"from_attributes": True}
