"""Normalized Alpaca market-data models. Never include credentials."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.models.schemas import DATA_UNAVAILABLE


class FreshnessStatus(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    INVALID = "INVALID"


class StockQuote(BaseModel):
    symbol: str
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_size: Optional[float] = None
    ask_size: Optional[float] = None
    last_trade_price: Optional[float] = None
    timestamp: Optional[datetime] = None
    received_at: Optional[datetime] = None
    source: str = "alpaca"
    freshness: FreshnessStatus = FreshnessStatus.DATA_UNAVAILABLE
    availability: str = DATA_UNAVAILABLE
    error: Optional[str] = None

    @property
    def usable(self) -> bool:
        return (
            self.availability != DATA_UNAVAILABLE
            and self.freshness == FreshnessStatus.FRESH
            and self.bid is not None
            and self.ask is not None
            and self.bid > 0
            and self.ask > 0
        )


class StockTrade(BaseModel):
    symbol: str
    price: Optional[float] = None
    size: Optional[float] = None
    timestamp: Optional[datetime] = None
    source: str = "alpaca"
    freshness: FreshnessStatus = FreshnessStatus.DATA_UNAVAILABLE
    availability: str = DATA_UNAVAILABLE
    error: Optional[str] = None


class StockBar(BaseModel):
    timestamp: Optional[datetime] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    vwap: Optional[float] = None


class MarketClock(BaseModel):
    is_open: Optional[bool] = None
    timestamp: Optional[datetime] = None
    next_open: Optional[str] = None
    next_close: Optional[str] = None
    session: Optional[str] = None
    source: str = "alpaca"
    availability: str = DATA_UNAVAILABLE
    error: Optional[str] = None


class OptionContract(BaseModel):
    occ_symbol: str
    underlying_symbol: str
    option_type: Optional[str] = None
    strike: Optional[float] = None
    expiration: Optional[str] = None
    multiplier: Optional[str] = None
    tradable: Optional[bool] = None
    status: Optional[str] = None
    open_interest: Optional[float] = None
    close_price: Optional[float] = None
    source: str = "alpaca"


class OptionSnapshot(BaseModel):
    occ_symbol: str
    bid: Optional[float] = None
    ask: Optional[float] = None
    last_price: Optional[float] = None
    volume: Optional[float] = None
    open_interest: Optional[float] = None
    implied_volatility: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None
    timestamp: Optional[datetime] = None
    received_at: Optional[datetime] = None
    source: str = "alpaca"
    freshness: FreshnessStatus = FreshnessStatus.DATA_UNAVAILABLE
    greeks_quality: str = DATA_UNAVAILABLE
    availability: str = DATA_UNAVAILABLE
    error: Optional[str] = None


class SelectedContract(BaseModel):
    underlying: str
    occ_symbol: str
    option_type: str
    strike: float
    expiration: str
    bid: Optional[float] = None
    ask: Optional[float] = None
    last_price: Optional[float] = None
    implied_volatility: Optional[float] = None
    greeks: Dict[str, Any] = Field(default_factory=dict)
    strategy_key: str = "directional_vertical_spread"
    selection_reason: str = ""
