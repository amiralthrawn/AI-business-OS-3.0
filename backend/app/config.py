from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> backend/app -> backend -> repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data_core.db"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    # Comma-separated list of frontend origins allowed to call this API
    # cross-origin (e.g. "https://ai-business-os.vercel.app"). Unset in local
    # dev -- see cors_allowed_origins() for the resulting fallback behavior.
    allowed_origins: str | None = None
    # V2.1 web sourcing: a Brave Search API key enables real web search for
    # supplier sourcing. Unset -> sourcing uses internal data only, and says so.
    brave_search_api_key: str | None = None
    # V3 Veilleur agent: Perplexity (Sonar) searches the live web. Unset ->
    # the Veilleur says it is not configured and finds nothing (never invents).
    perplexity_api_key: str | None = None
    perplexity_model: str = "sonar"
    # Same role, through Google Gemini with Google Search grounding. When this
    # key is set it is used first (app.agents.perplexity.ask).
    # OpenRouter gives one key for many models; perplexity/sonar searches the
    # web and returns its sources. Used first when set.
    openrouter_api_key: str | None = None
    openrouter_model: str = "perplexity/sonar"
    browserbase_api_key: str | None = None  # cloud browser for the AI browser agent
    browserbase_project_id: str | None = None
    browser_local: bool = False  # dev only: drive a local Chromium instead of the cloud
    browser_local_executable: str | None = None
    openrouter_guide_model: str = "perplexity/sonar-pro"  # the connection guide: more reliable than the light search model
    openrouter_agent_model: str = "google/gemini-2.5-flash"  # the Veilleur's reasoning model (needs tool calling)
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    # Runs the agents around the clock (app.agents.scheduler).
    agents_scheduler: bool = True
    # V3 authentication (app.auth). "required": every API call needs a
    # signed-in user's token and only sees that user's company. "legacy": the
    # V2 behavior (no sign-in, X-User-Id profile switcher, one company) --
    # kept for the bundled demo and the test suite, never for real customers.
    auth_mode: str = "required"
    # Signs the access tokens. Required in "required" mode; generate one with
    # `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
    auth_secret_key: str | None = None
    access_token_ttl_hours: int = 12
    invite_ttl_days: int = 7
    # Whether anyone can create a new company from the sign-up page.
    signup_enabled: bool = True
    # Where invitation links point (the frontend).
    frontend_url: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=str(ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    @field_validator("database_url")
    @classmethod
    def _sqlalchemy_url(cls, value: str) -> str:
        """Hosted PostgreSQL (e.g. Render) hands out `postgres://` or
        `postgresql://` URLs; SQLAlchemy 2 rejects the first and would pick
        the absent psycopg2 driver for the second. Both are pointed at the
        installed psycopg 3 driver. SQLite and explicit drivers are untouched."""

        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value

    def cors_allowed_origins(self) -> list[str] | None:
        """Parses `allowed_origins` into a list, or `None` when unset.
        `None` is a deliberate third state (distinct from an empty list):
        it tells the CORS setup in `app.main` to fall back to the
        localhost/127.0.0.1-only dev regex instead of an explicit origin
        list, so a deployed backend with `ALLOWED_ORIGINS` set never also
        trusts "http://localhost:*"."""

        if not self.allowed_origins:
            return None
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
