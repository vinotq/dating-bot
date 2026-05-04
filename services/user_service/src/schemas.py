import uuid

from pydantic import BaseModel, Field, field_validator, model_validator


class UserCreate(BaseModel):
    telegram_id: int
    username: str | None = None
    referral_code: str | None = None


class UserOut(BaseModel):
    id: uuid.UUID
    telegram_id: int
    username: str | None
    is_active: bool
    referral_code: str | None = None

    model_config = {"from_attributes": True}


class ProfileCreate(BaseModel):
    user_id: uuid.UUID
    name: str = Field(min_length=2, max_length=100)
    age: int = Field(ge=14)
    gender: str
    city: str = Field(min_length=1, max_length=100)
    bio: str | None = Field(default=None, max_length=500)
    looking_for_gender: str = "any"
    age_min: int = Field(default=14, ge=14)
    age_max: int = Field(default=-1)

    @field_validator("age_max")
    @classmethod
    def validate_age_max_create(cls, value: int) -> int:
        if value == -1 or value >= 14:
            return value
        raise ValueError("age_max must be -1 (no upper limit) or >= 14")

    @model_validator(mode="after")
    def age_prefs_order_create(self) -> "ProfileCreate":
        if self.age_max != -1 and self.age_min > self.age_max:
            raise ValueError("age_min must not exceed age_max")
        return self

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str) -> str:
        if value not in {"male", "female", "other"}:
            raise ValueError("gender must be male, female or other")
        return value

    @field_validator("looking_for_gender")
    @classmethod
    def validate_looking_for_gender(cls, value: str) -> str:
        if value not in {"male", "female", "any"}:
            raise ValueError("looking_for_gender must be male, female or any")
        return value


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    age: int | None = Field(default=None, ge=14)
    gender: str | None = None
    city: str | None = Field(default=None, min_length=1, max_length=100)
    bio: str | None = Field(default=None, max_length=500)
    looking_for_gender: str | None = None
    age_min: int | None = Field(default=None, ge=14)
    age_max: int | None = Field(default=None)

    @field_validator("age_max")
    @classmethod
    def validate_age_max_update(cls, value: int | None) -> int | None:
        if value is None or value == -1 or value >= 14:
            return value
        raise ValueError("age_max must be -1 (no upper limit) or >= 14")


class ProfileOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    age: int
    gender: str
    city: str
    bio: str | None
    looking_for_gender: str
    age_min: int
    age_max: int
    completeness_score: int

    model_config = {"from_attributes": True}


class PhotoOut(BaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    s3_key: str
    s3_url: str
    is_primary: bool
    display_order: int

    model_config = {"from_attributes": True}


class PhotoOrderUpdate(BaseModel):
    photo_ids: list[uuid.UUID] = Field(min_length=0)


class PreferencesUpdate(BaseModel):
    looking_for_gender: str
    age_min: int = Field(ge=14)
    age_max: int = Field()

    @field_validator("age_max")
    @classmethod
    def validate_age_max_prefs(cls, value: int) -> int:
        if value == -1 or value >= 14:
            return value
        raise ValueError("age_max must be -1 (no upper limit) or >= 14")

    @model_validator(mode="after")
    def age_prefs_order_prefs(self) -> "PreferencesUpdate":
        if self.age_max != -1 and self.age_min > self.age_max:
            raise ValueError("age_min must not exceed age_max")
        return self


class InterestCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class InterestOut(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class UserInterestsUpdate(BaseModel):
    interest_ids: list[int] = Field(min_length=1)
