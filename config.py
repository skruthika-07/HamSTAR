from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./hamstar.db"

    mistral_api_key: str = ""
    mistral_ocr_model: str = "mistral-ocr-latest"
    mistral_chat_model: str = "ministral-14b-latest"

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"

    jwt_secret: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    # comma-separated list of allowed origins
    frontend_url: str = "http://localhost:5173"

    upload_dir: str = "uploads"
    max_upload_size_mb: int = 20

    # a conclusion needs MORE than this (per cent)
    understanding_threshold: float = 70

    ai_timeout_seconds: float = 45
    ai_max_retries: int = 3

    tiara_for_certificate: int = 500

    # outgoing email (password reset codes). Gmail: smtp.gmail.com, port 587, and an app password
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    reset_code_minutes: int = 15
    # the hourly job that emails a reminder the day before a task's deadline
    reminders_enabled: bool = True

    @property
    def threshold(self) -> float:
        return self.understanding_threshold / 100

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_url.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
