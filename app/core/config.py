from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    app_name: str = "Adaptive Interview Simulator"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    # Interview
    min_interview_turns: int = Field(default=8, ge=8)
    max_interview_turns: int = Field(default=12, ge=8)

    # Database
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/"
        "adaptive_interview"
    )

    # AI providers
    gemini_api_key: str = ""
    groq_api_key: str = ""
    claude_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()