"""Application configuration via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/superintendent_finder"
    database_url_sync: str = (
        "postgresql://postgres:postgres@localhost:5432/superintendent_finder"
    )

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Mailgun
    mailgun_api_key: str = ""
    mailgun_domain: str = ""
    mailgun_sender_email: str = ""
    mailgun_webhook_signing_key: str = ""

    # Application
    app_name: str = "Superintendent Finder"
    app_physical_address: str = ""
    secret_key: str = "change-me-to-a-random-secret-key"

    # Email Limits
    daily_email_limit: int = 100
    warmup_phase: bool = True

    # JWT
    access_token_expire_minutes: int = 60


settings = Settings()
