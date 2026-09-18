"""Production-safe CORS and database URL helpers. No secrets."""

from app.config import LOCAL_DEV_ORIGINS, Settings, build_cors_origins, normalize_database_url, parse_origin_list
from app.utils.logging import KwargsLogger


def test_wildcard_cors_is_rejected():
    assert "*" not in parse_origin_list("https://app.example,*")
    assert parse_origin_list('["https://app.example"]') == ["https://app.example"]
    assert parse_origin_list("https://a.example, https://b.example") == [
        "https://a.example",
        "https://b.example",
    ]


def test_production_cors_excludes_localhost():
    origins = build_cors_origins(
        frontend_url="https://trade-ai.example",
        extra=["https://preview.example"],
        environment="production",
    )
    assert origins[0] == "https://trade-ai.example"
    assert "https://preview.example" in origins
    assert "http://localhost:3000" not in origins
    assert "*" not in origins


def test_development_cors_includes_localhost():
    origins = build_cors_origins(frontend_url="", extra=[], environment="development")
    for origin in LOCAL_DEV_ORIGINS:
        assert origin in origins


def test_postgres_url_driver_normalization():
    assert normalize_database_url("postgres://user:pass@host:5432/db").startswith("postgresql+psycopg://")
    assert normalize_database_url("postgresql://user:pass@host:5432/db").startswith("postgresql+psycopg://")
    already = "postgresql+psycopg://user:pass@host:5432/db"
    assert normalize_database_url(already) == already


def test_settings_repr_hides_secrets():
    loaded = Settings(
        alpaca_api_key="not-a-real-key",
        alpaca_secret_key="not-a-real-secret",
        llm_api_key="not-a-real-llm-key",
        database_url="postgresql+psycopg://user:pass@localhost:5432/tradeguard",
    )
    blob = repr(loaded)
    assert "not-a-real-key" not in blob
    assert "not-a-real-secret" not in blob
    assert "not-a-real-llm-key" not in blob
    assert "pass@" not in blob


def test_logger_redacts_secret_fields():
    logger = KwargsLogger("deploy-test")
    fields = {"alpaca_api_key": "abc", "database_url": "postgresql+psycopg://u:p@h/db", "path": "/health"}
    redacted = {key: logger._redact(key, value) for key, value in fields.items()}
    assert redacted["alpaca_api_key"] == "[redacted]"
    assert redacted["database_url"] == "[redacted]"
    assert redacted["path"] == "/health"
