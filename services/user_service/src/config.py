from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://dating_user:dating_pass@postgres:5432/dating_bot"  # env: DATABASE_URL

    minio_endpoint: str = "minio:9000"
    minio_public_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "dating-photos"
    minio_use_ssl: bool = False
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    redis_dsn: str = "redis://redis:6379/0"
    minio_thumb_bucket: str = "dating-thumbnails"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
