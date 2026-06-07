from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Groq ──────────────────────────────────────────────────────────────────
    groq_api_key: str
    groq_model: str = Field(default="llama-3.3-70b-versatile")

    # ── GitHub ────────────────────────────────────────────────────────────────
    github_token: str

    # ── LangChain / LangSmith ─────────────────────────────────────────────────
    langchain_api_key: str
    langchain_tracing_v2: bool = True
    langchain_endpoint: str = "https://api.smith.langchain.com"
    langchain_project: str = "autopilot_dev"

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379"

    # ── FastAPI ───────────────────────────────────────────────────────────────
    fastapi_host: str = "0.0.0.0"
    fastapi_port: int = 8000

    # ── General ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    env: str = "development"
    max_fix_retries: int = Field(default=3)


# Single shared instance — import this everywhere
settings = Settings()
