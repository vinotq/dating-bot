from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_bot_token: str = ""
    user_service_url: str = "http://user_service:8000"
    ranking_service_url: str = "http://ranking_service:8000"
    matching_service_url: str = "http://matching_service:8000"
    redis_dsn: str = "redis://redis:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
