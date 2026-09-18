"""Shared enumerations for TradeGuard AI."""

from enum import Enum


class TradingMode(str, Enum):
    """Trading mode enumeration."""

    NORMAL = "normal"
    PROTECTION = "protection"
    CRITICAL = "critical"
