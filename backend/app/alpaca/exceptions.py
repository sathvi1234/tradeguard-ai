"""Alpaca integration exceptions."""


class AlpacaError(Exception):
    """Base Alpaca error. Message must never include credentials."""


class AlpacaConfigError(AlpacaError):
    """Missing or invalid Alpaca configuration."""


class AlpacaAuthError(AlpacaError):
    """Alpaca authentication failed."""


class AlpacaLiveTradingBlocked(AlpacaError):
    """Attempted live trading endpoint or live-mode configuration."""


class AlpacaRateLimitError(AlpacaError):
    """Alpaca returned HTTP 429."""


class AlpacaDataUnavailable(AlpacaError):
    """Requested market or options data is not available."""
