from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+asyncpg://dating_user:dating_pass@postgres:5432/dating_bot"
    )
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    redis_dsn: str = "redis://redis:6379/0"
    user_service_url: str = "http://user_service:8000"
    matching_service_url: str = "http://matching_service:8000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
