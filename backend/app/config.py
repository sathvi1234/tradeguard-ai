"""TradeGuard AI Configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"

PAPER_API_URL = "https://paper-api.alpaca.markets"
LIVE_API_URL = "https://api.alpaca.markets"
DATA_API_URL = "https://data.alpaca.markets"
IEX_STREAM_URL = "wss://stream.data.alpaca.markets/v2/iex"

LOCAL_DEV_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
]

QUOTE_MAX_AGE_SECONDS = 300
OPTION_QUOTE_MAX_AGE_SECONDS = 300
MAX_OPTION_SPREAD_PCT = 0.15
PREFERRED_DTE_MIN = 7
PREFERRED_DTE_MAX = 45
DEFAULT_WATCHLIST = ["SPY", "QQQ", "AAPL"]


def parse_origin_list(value: Any) -> List[str]:
    """Parse CORS origins from JSON, CSV, or a list. Never returns '*'."""
    if value is None or value == "":
        return []
    items: List[str] = []
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = [part.strip() for part in text.split(",")]
            if isinstance(parsed, list):
                items = [str(part) for part in parsed]
            else:
                items = [text]
        else:
            items = [part.strip() for part in text.split(",")]
    elif isinstance(value, (list, tuple, set)):
        items = [str(part) for part in value]
    else:
        items = [str(value)]
    cleaned: List[str] = []
    for item in items:
        origin = item.strip().rstrip("/")
        if not origin or origin == "*":
            continue
        if origin not in cleaned:
            cleaned.append(origin)
    return cleaned


def build_cors_origins(*, frontend_url: str = "", extra: Any = None, environment: str = "development") -> List[str]:
    """Production: FRONTEND_URL + CORS_ORIGINS only. Local: also allow localhost Next.js."""
    origins = parse_origin_list(extra)
    front = (frontend_url or "").strip().rstrip("/")
    if front and front != "*" and front not in origins:
        origins.insert(0, front)
    if (environment or "development").strip().lower() != "production":
        for origin in LOCAL_DEV_ORIGINS:
            if origin not in origins:
                origins.append(origin)
    return origins


def normalize_database_url(raw: str) -> str:
    """Accept Render/Heroku postgres:// URLs and pin the psycopg3 SQLAlchemy driver."""
    value = (raw or "").strip()
    if not value:
        return value
    if value.startswith("postgres://"):
        value = "postgresql+psycopg://" + value[len("postgres://") :]
    elif value.startswith("postgresql://") and "+psycopg" not in value.split("://", 1)[0]:
        value = "postgresql+psycopg://" + value[len("postgresql://") :]
    return value


class Settings(BaseSettings):
    """Application settings loaded from backend/.env and process environment."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    app_name: str = "TradeGuard AI"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    frontend_url: str = ""
    cors_origins: List[str] = Field(default_factory=list)

    alpaca_api_key: str = Field(default="", repr=False)
    alpaca_secret_key: str = Field(default="", repr=False)
    alpaca_paper_trade: bool = True
    alpaca_base_url: str = PAPER_API_URL
    alpaca_data_url: str = DATA_API_URL
    dry_run: bool = True
    watchlist: List[str] = Field(default_factory=lambda: list(DEFAULT_WATCHLIST))
    quote_max_age_seconds: int = QUOTE_MAX_AGE_SECONDS
    option_quote_max_age_seconds: int = OPTION_QUOTE_MAX_AGE_SECONDS
    max_option_spread_pct: float = MAX_OPTION_SPREAD_PCT
    preferred_dte_min: int = PREFERRED_DTE_MIN
    preferred_dte_max: int = PREFERRED_DTE_MAX

    llm_provider: str = "groq"
    llm_api_key: str = Field(
        default="",
        repr=False,
        validation_alias=AliasChoices("LLM_API_KEY", "GROQ_API_KEY", "llm_api_key"),
    )
    llm_model: str = "llama-3.1-8b-instant"
    demo_user_email: str = "demo@tradeai.local"
    database_url: str = Field(default="", repr=False)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: Any) -> List[str]:
        return parse_origin_list(value)

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: Any) -> str:
        return normalize_database_url("" if value is None else str(value))

    @model_validator(mode="after")
    def _finalize_cors(self) -> "Settings":
        origins = build_cors_origins(
            frontend_url=self.frontend_url,
            extra=self.cors_origins,
            environment=self.environment,
        )
        object.__setattr__(self, "cors_origins", origins)
        return self

    def env_file_loaded(self) -> bool:
        """Return True when backend/.env exists on disk."""
        return ENV_FILE.is_file()

    def alpaca_keys_configured(self) -> bool:
        """Return True when both Alpaca credentials are non-empty. Never logs values."""
        return bool(self.alpaca_api_key.strip() and self.alpaca_secret_key.strip())

    def is_paper_url(self) -> bool:
        """Return True when the configured base URL is the Alpaca paper API."""
        return self.alpaca_base_url.rstrip("/").lower() == PAPER_API_URL

    def llm_configured(self) -> bool:
        """True when Groq is selected and an API key is present. Never logs the key."""
        return (
            self.llm_provider.strip().lower() == "groq"
            and bool(self.llm_api_key.strip())
        )

    def live_trading_blocked(self) -> bool:
        """Live trading must stay disabled."""
        url = self.alpaca_base_url.rstrip("/").lower()
        return (not self.alpaca_paper_trade) or url == LIVE_API_URL or "paper" not in url


settings = Settings()
