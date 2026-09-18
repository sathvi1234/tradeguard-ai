"""Logging utilities."""

import logging
import sys
from typing import Any, Dict, Optional


_RESERVED = {"exc_info", "stack_info", "stacklevel", "extra"}
_REDACT_FRAGMENTS = (
    "alpaca_api_key",
    "alpaca_secret",
    "llm_api_key",
    "groq_api_key",
    "api_key",
    "secret_key",
    "password",
    "authorization",
    "database_url",
    "access_token",
)


class KwargsLogger(logging.Logger):
    """Logger that accepts structlog-style keyword fields without crashing."""

    def _redact(self, key: str, value: Any) -> Any:
        lowered = key.lower()
        if any(fragment in lowered for fragment in _REDACT_FRAGMENTS):
            return "[redacted]"
        text = str(value)
        if "://" in text and "@" in text:
            return "[redacted-url]"
        return value

    def _strip_fields(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        fields = {key: self._redact(key, kwargs.pop(key)) for key in list(kwargs) if key not in _RESERVED}
        if fields:
            extra = dict(kwargs.get("extra") or {})
            extra.update(fields)
            kwargs["extra"] = extra
        return kwargs

    def _safe_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        kwargs = self._strip_fields(kwargs)
        extra = kwargs.get("extra")
        if extra:
            # Avoid KeyError from LogRecord for unknown extra keys.
            suffix = " ".join(f"{k}={v}" for k, v in extra.items())
            kwargs.pop("extra", None)
            return kwargs, suffix
        return kwargs, ""

    def debug(self, msg, *args, **kwargs):
        kwargs, suffix = self._safe_kwargs(kwargs)
        if suffix:
            msg = f"{msg} {suffix}"
        return super().debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        kwargs, suffix = self._safe_kwargs(kwargs)
        if suffix:
            msg = f"{msg} {suffix}"
        return super().info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        kwargs, suffix = self._safe_kwargs(kwargs)
        if suffix:
            msg = f"{msg} {suffix}"
        return super().warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        kwargs, suffix = self._safe_kwargs(kwargs)
        if suffix:
            msg = f"{msg} {suffix}"
        return super().error(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        kwargs, suffix = self._safe_kwargs(kwargs)
        if suffix:
            msg = f"{msg} {suffix}"
        return super().critical(msg, *args, **kwargs)


logging.setLoggerClass(KwargsLogger)


def setup_logging(log_level: str = "INFO") -> None:
    """Setup application logging."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    try:
        handler.stream.reconfigure(errors="replace")
    except Exception:
        pass
    logging.basicConfig(
        level=log_level,
        handlers=[handler],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Get logger instance."""
    return logging.getLogger(name)


def log_risk_event(
    event_type: str,
    severity: str,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """Log a risk event."""
    logger = get_logger("risk")
    message = f"[{severity.upper()}] {event_type}"
    if data:
        message += f" {data}"

    if severity == "critical":
        logger.critical(message)
    elif severity == "high":
        logger.error(message)
    elif severity == "medium":
        logger.warning(message)
    else:
        logger.info(message)


def log_security_event(
    event_type: str,
    data: Optional[Dict[str, Any]] = None,
    severity: str = "info",
) -> None:
    """Log a security event."""
    logger = get_logger("security")
    message = f"[SECURITY] {event_type}"
    if data:
        message += f" {data}"

    if severity == "critical":
        logger.critical(message)
    else:
        logger.warning(message)
