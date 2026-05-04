from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://dating_user:dating_pass@postgres:5432/dating_bot"
    redis_dsn: str = "redis://redis:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    feed_size: int = 10
    feed_ttl: int = 1800
    matching_service_url: str = "http://matching_service:8000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
