import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class SwipeCreate(BaseModel):
    swiper_id: uuid.UUID
    swiped_id: uuid.UUID
    action: str

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in {"like", "skip"}:
            raise ValueError("action must be 'like' or 'skip'")
        return v


class SwipeResult(BaseModel):
    is_match: bool
    match_id: uuid.UUID | None = None


class MatchOut(BaseModel):
    id: uuid.UUID
    user1_id: uuid.UUID
    user2_id: uuid.UUID
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    match_id: uuid.UUID
    sender_id: uuid.UUID
    body: str


class MessageOut(BaseModel):
    id: uuid.UUID
    match_id: uuid.UUID
    sender_id: uuid.UUID
    body: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
