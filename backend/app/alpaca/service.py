"""Alpaca API service wrapper."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.alpaca.client import AlpacaClient
from app.alpaca.exceptions import AlpacaDataUnavailable, AlpacaError, AlpacaRateLimitError
from app.alpaca.freshness import evaluate_freshness, parse_alpaca_time
from app.config import settings
from app.models.market_data import (
    FreshnessStatus,
    MarketClock,
    OptionContract,
    OptionSnapshot,
    StockBar,
    StockQuote,
    StockTrade,
)
from app.models.schemas import DATA_UNAVAILABLE
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _opt_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _opt_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    return bool(value)


class AlpacaService:
    """Wrapper for Alpaca paper API interactions."""

    def __init__(self) -> None:
        self.logger = logger
        self._client: Optional[AlpacaClient] = None

    @property
    def client(self) -> AlpacaClient:
        if self._client is None:
            self._client = AlpacaClient()
        return self._client

    def _map_account(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        cash = _to_float(raw.get("cash"))
        buying_power = _to_float(raw.get("buying_power"))
        portfolio_value = _to_float(raw.get("portfolio_value"))
        equity = _to_float(raw.get("equity"))
        if portfolio_value <= 0 and equity > 0:
            portfolio_value = equity

        return {
            "status": raw.get("status"),
            "account_status": raw.get("status"),
            "cash": cash,
            "buying_power": buying_power,
            "portfolio_value": portfolio_value,
            "equity": equity,
            "currency": raw.get("currency"),
            "trading_blocked": bool(raw.get("trading_blocked")),
            "account_blocked": bool(raw.get("account_blocked")),
            "paper_trading_allowed": True,
            "paper_trading": True,
            "dry_run": settings.dry_run,
            "live_trading": False,
        }

    async def get_account(self) -> Optional[Dict[str, Any]]:
        """Get paper trading account information from Alpaca."""
        try:
            raw = await self.client.get_account()
            return self._map_account(raw)
        except AlpacaError as exc:
            logger.error("Failed to get Alpaca account: %s", exc)
            return None
        except Exception as exc:
            logger.error("Unexpected Alpaca account error: %s", type(exc).__name__)
            return None

    async def get_status(self) -> Dict[str, Any]:
        """Connection health for the paper trading API. Never includes credentials."""
        status: Dict[str, Any] = {
            "healthy": False,
            "connected": False,
            "authenticated": False,
            "paper_trading": True,
            "paper_trading_allowed": True,
            "dry_run": settings.dry_run,
            "live_trading": False,
            "base_url": settings.alpaca_base_url,
            "env_file_present": settings.env_file_loaded(),
            "keys_configured": settings.alpaca_keys_configured(),
            "account_status": None,
            "error": None,
        }

        if not settings.alpaca_paper_trade or not settings.is_paper_url():
            status["error"] = "Paper trading is not correctly configured"
            return status

        if not settings.alpaca_keys_configured():
            status["error"] = "Alpaca API credentials are not configured"
            return status

        try:
            account = await self.get_account()
        except Exception:
            status["error"] = "Alpaca paper API request failed"
            return status

        if not account:
            status["error"] = "Alpaca paper API authentication or account lookup failed"
            return status

        status.update(
            {
                "healthy": True,
                "connected": True,
                "authenticated": True,
                "account_status": account.get("status"),
                "cash_detected": account.get("cash") is not None,
                "buying_power_detected": account.get("buying_power") is not None,
                "portfolio_value_detected": account.get("portfolio_value") is not None,
                "equity_detected": account.get("equity") is not None,
            }
        )
        return status

    async def get_market_clock(self) -> MarketClock:
        try:
            raw = await self.client.get_clock()
            ts = parse_alpaca_time(raw.get("timestamp"))
            clock = MarketClock(
                is_open=bool(raw.get("is_open")) if "is_open" in raw else None,
                timestamp=ts,
                next_open=raw.get("next_open"),
                next_close=raw.get("next_close"),
                availability="AVAILABLE",
            )
            from app.services.market_snapshot import classify_session

            clock.session = classify_session(clock)
            return clock
        except AlpacaRateLimitError:
            return MarketClock(availability=DATA_UNAVAILABLE, error="rate_limited")
        except AlpacaError as exc:
            return MarketClock(availability=DATA_UNAVAILABLE, error=str(exc))

    async def get_asset(self, symbol: str) -> Optional[Dict[str, Any]]:
        key = symbol.upper()
        cache = getattr(self, "_asset_cache", None)
        if cache is None:
            self._asset_cache = {}
            cache = self._asset_cache
        if key in cache:
            return cache[key]
        try:
            asset = await self.client.get_asset(key)
        except AlpacaError:
            cache[key] = None
            return None
        cache[key] = asset
        return asset

    async def get_company_name(self, symbol: str) -> Optional[str]:
        asset = await self.get_asset(symbol)
        if not asset:
            return None
        name = asset.get("name") or asset.get("symbol")
        return str(name) if name else None

    def _quote_from_raw(self, symbol: str, raw: Any, received: datetime) -> StockQuote:
        payload = raw if isinstance(raw, dict) else {}
        quote = payload.get("quote") if isinstance(payload.get("quote"), dict) else payload
        ts = parse_alpaca_time(quote.get("t") or quote.get("timestamp"))
        freshness = evaluate_freshness(ts, max_age_seconds=settings.quote_max_age_seconds)
        bid = _opt_float(quote.get("bp") if quote.get("bp") is not None else quote.get("bid"))
        ask = _opt_float(quote.get("ap") if quote.get("ap") is not None else quote.get("ask"))
        if bid is None or ask is None or bid <= 0 or ask <= 0:
            return StockQuote(
                symbol=symbol,
                bid=bid,
                ask=ask,
                timestamp=ts,
                received_at=received,
                freshness=FreshnessStatus.INVALID if ts else FreshnessStatus.DATA_UNAVAILABLE,
                availability=DATA_UNAVAILABLE,
                error="invalid_quote" if ts else "not_found",
            )
        return StockQuote(
            symbol=symbol,
            bid=bid,
            ask=ask,
            bid_size=_opt_float(quote.get("bs") if quote.get("bs") is not None else quote.get("bid_size")),
            ask_size=_opt_float(quote.get("as") if quote.get("as") is not None else quote.get("ask_size")),
            timestamp=ts,
            received_at=received,
            freshness=freshness,
            availability="AVAILABLE",
        )

    def _trade_from_raw(self, symbol: str, raw: Any) -> StockTrade:
        payload = raw if isinstance(raw, dict) else {}
        trade = payload.get("trade") if isinstance(payload.get("trade"), dict) else payload
        ts = parse_alpaca_time(trade.get("t") or trade.get("timestamp"))
        price = _opt_float(trade.get("p") if trade.get("p") is not None else trade.get("price"))
        freshness = evaluate_freshness(ts, max_age_seconds=settings.quote_max_age_seconds)
        availability = "AVAILABLE" if price is not None else DATA_UNAVAILABLE
        return StockTrade(
            symbol=symbol,
            price=price,
            size=_opt_float(trade.get("s") if trade.get("s") is not None else trade.get("size")),
            timestamp=ts,
            freshness=freshness,
            availability=availability,
        )

    async def get_latest_quote(self, symbol: str) -> StockQuote:
        received = datetime.now(timezone.utc)
        from app.services.market_snapshot import DATA_FEED

        try:
            raw = await self.client.get_latest_stock_quote(symbol, feed=DATA_FEED)
            return self._quote_from_raw(symbol, raw, received)
        except AlpacaRateLimitError:
            return StockQuote(symbol=symbol, availability=DATA_UNAVAILABLE, freshness=FreshnessStatus.DATA_UNAVAILABLE, error="rate_limited", received_at=received)
        except AlpacaDataUnavailable:
            return StockQuote(symbol=symbol, availability=DATA_UNAVAILABLE, freshness=FreshnessStatus.DATA_UNAVAILABLE, error="not_found", received_at=received)
        except AlpacaError:
            try:
                raw = await self.client.get_latest_stock_quote(symbol, feed="")
                return self._quote_from_raw(symbol, raw, received)
            except AlpacaRateLimitError:
                return StockQuote(symbol=symbol, availability=DATA_UNAVAILABLE, freshness=FreshnessStatus.DATA_UNAVAILABLE, error="rate_limited", received_at=received)
            except AlpacaDataUnavailable:
                return StockQuote(symbol=symbol, availability=DATA_UNAVAILABLE, freshness=FreshnessStatus.DATA_UNAVAILABLE, error="not_found", received_at=received)
            except AlpacaError as exc:
                return StockQuote(symbol=symbol, availability=DATA_UNAVAILABLE, freshness=FreshnessStatus.DATA_UNAVAILABLE, error=str(exc), received_at=received)

    async def get_latest_trade(self, symbol: str) -> StockTrade:
        from app.services.market_snapshot import DATA_FEED

        try:
            raw = await self.client.get_latest_stock_trade(symbol, feed=DATA_FEED)
            return self._trade_from_raw(symbol, raw)
        except AlpacaRateLimitError:
            return StockTrade(symbol=symbol, availability=DATA_UNAVAILABLE, freshness=FreshnessStatus.DATA_UNAVAILABLE, error="rate_limited")
        except AlpacaError:
            try:
                raw = await self.client.get_latest_stock_trade(symbol, feed="")
                return self._trade_from_raw(symbol, raw)
            except AlpacaRateLimitError:
                return StockTrade(symbol=symbol, availability=DATA_UNAVAILABLE, freshness=FreshnessStatus.DATA_UNAVAILABLE, error="rate_limited")
            except AlpacaError as exc:
                return StockTrade(symbol=symbol, availability=DATA_UNAVAILABLE, freshness=FreshnessStatus.DATA_UNAVAILABLE, error=str(exc))

    def _bars_from_raw(self, raw_bars: Any, symbol: str) -> List[StockBar]:
        bars = raw_bars or []
        if isinstance(bars, dict):
            bars = bars.get(symbol) or bars.get(symbol.upper()) or next(iter(bars.values()), [])
        out: List[StockBar] = []
        for bar in bars or []:
            if not isinstance(bar, dict):
                continue
            out.append(
                StockBar(
                    timestamp=parse_alpaca_time(bar.get("t")),
                    open=_opt_float(bar.get("o")),
                    high=_opt_float(bar.get("h")),
                    low=_opt_float(bar.get("l")),
                    close=_opt_float(bar.get("c")),
                    volume=_opt_float(bar.get("v")),
                    vwap=_opt_float(bar.get("vw")),
                )
            )
        return out

    async def get_bars_range(
        self,
        symbol: str,
        start: str,
        end: str,
        timeframe: str = "1Day",
        limit: int = 10000,
    ) -> List[StockBar]:
        """Historical bars for a date range. Never invents prices. No live orders."""
        from app.services.market_snapshot import DATA_FEED

        collected: List[StockBar] = []
        page_token: Optional[str] = None
        for _ in range(20):
            try:
                raw = await self.client.get_stock_bars(
                    symbol,
                    timeframe=timeframe,
                    limit=min(limit, 10000),
                    start=start,
                    end=end,
                    page_token=page_token,
                    feed=DATA_FEED,
                )
            except AlpacaError:
                try:
                    raw = await self.client.get_stock_bars(
                        symbol,
                        timeframe=timeframe,
                        limit=min(limit, 10000),
                        start=start,
                        end=end,
                        page_token=page_token,
                        feed="",
                    )
                except AlpacaError:
                    break
            chunk = self._bars_from_raw(raw.get("bars") if isinstance(raw, dict) else None, symbol)
            collected.extend(chunk)
            page_token = raw.get("next_page_token") if isinstance(raw, dict) else None
            if not page_token or len(collected) >= limit:
                break
        seen = set()
        unique: List[StockBar] = []
        for bar in collected:
            key = bar.timestamp.isoformat() if bar.timestamp else None
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            unique.append(bar)
        unique.sort(key=lambda item: item.timestamp or datetime.min.replace(tzinfo=timezone.utc))
        return unique[:limit]

    async def get_bars(self, symbol: str, timeframe: str = "1Day", limit: int = 60) -> List[StockBar]:
        from app.services.market_snapshot import DATA_FEED, bars_start_iso

        try:
            raw = await self.client.get_stock_bars(
                symbol,
                timeframe=timeframe,
                limit=limit,
                start=bars_start_iso(),
                feed=DATA_FEED,
            )
            return self._bars_from_raw(raw.get("bars"), symbol)
        except AlpacaError:
            try:
                raw = await self.client.get_stock_bars(
                    symbol,
                    timeframe=timeframe,
                    limit=limit,
                    start=bars_start_iso(),
                    feed="",
                )
                return self._bars_from_raw(raw.get("bars"), symbol)
            except AlpacaError:
                return []

    async def snapshot_symbol(self, symbol: str, clock: Optional[MarketClock] = None) -> Dict[str, Any]:
        from app.services.market_snapshot import DATA_FEED, snapshot_from_parts

        underlying = symbol.upper()
        quote = await self.get_latest_quote(underlying)
        trade = await self.get_latest_trade(underlying)
        bars = await self.get_bars(underlying, timeframe="1Day", limit=60)
        company = await self.get_company_name(underlying)
        market_clock = clock or await self.get_market_clock()
        if quote.last_trade_price is None and trade.price is not None:
            quote.last_trade_price = trade.price
        return snapshot_from_parts(underlying, quote, trade, market_clock, bars, company, feed=DATA_FEED)

    async def snapshot_watchlist(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Batch IEX quotes/trades/bars so the watchlist is not emptied by per-symbol rate limits."""
        from app.services.market_snapshot import DATA_FEED, bars_start_iso, snapshot_from_parts

        received = datetime.now(timezone.utc)
        clock = await self.get_market_clock()
        quotes_map: Dict[str, Any] = {}
        trades_map: Dict[str, Any] = {}
        bars_map: Dict[str, Any] = {}
        try:
            quotes_map = (await self.client.get_latest_stock_quotes(symbols, feed=DATA_FEED)).get("quotes") or {}
        except AlpacaError:
            quotes_map = {}
        try:
            trades_map = (await self.client.get_latest_stock_trades(symbols, feed=DATA_FEED)).get("trades") or {}
        except AlpacaError:
            trades_map = {}
        try:
            bars_map = (
                await self.client.get_stock_bars_multi(
                    symbols,
                    timeframe="1Day",
                    limit=60,
                    start=bars_start_iso(),
                    feed=DATA_FEED,
                )
            ).get("bars") or {}
        except AlpacaError:
            bars_map = {}

        if not quotes_map and not trades_map:
            rows: List[Dict[str, Any]] = []
            for symbol in symbols:
                rows.append(await self.snapshot_symbol(symbol, clock=clock))
            return rows

        items: List[Dict[str, Any]] = []
        for symbol in symbols:
            key = symbol.upper()
            quote = self._quote_from_raw(key, quotes_map.get(key) or quotes_map.get(symbol) or {}, received)
            trade = self._trade_from_raw(key, trades_map.get(key) or trades_map.get(symbol) or {})
            bars = self._bars_from_raw(bars_map.get(key) or bars_map.get(symbol) or [], key)
            if len(bars) < 2:
                bars = await self.get_bars(key, timeframe="1Day", limit=60)
            company = await self.get_company_name(key)
            if quote.last_trade_price is None and trade.price is not None:
                quote.last_trade_price = trade.price
            items.append(snapshot_from_parts(key, quote, trade, clock, bars, company, feed=DATA_FEED))
        return items

    async def get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Normalized underlying quote for Market Scout. Last trade is enough; bid/ask are optional."""
        from app.alpaca.iex_stream import overlay_snapshot

        snap = overlay_snapshot(await self.snapshot_symbol(symbol))
        last = snap.get("price") if isinstance(snap.get("price"), (int, float)) else snap.get("last_trade_price")
        bid = snap.get("bid") if isinstance(snap.get("bid"), (int, float)) else None
        ask = snap.get("ask") if isinstance(snap.get("ask"), (int, float)) else None
        mid = (bid + ask) / 2 if bid and ask else None
        current = last if isinstance(last, (int, float)) else mid
        missing = []
        if not isinstance(current, (int, float)):
            missing.append("price")
        integrity = snap.get("integrity") if isinstance(snap.get("integrity"), dict) else {}
        fail_closed = bool(snap.get("integrity_fail_closed") or integrity.get("fail_closed"))
        return {
            "symbol": symbol,
            "ask_price": ask,
            "bid_price": bid,
            "ask_size": snap.get("ask_size"),
            "bid_size": snap.get("bid_size"),
            "last_trade_price": last if isinstance(last, (int, float)) else None,
            "current_price": current if isinstance(current, (int, float)) else None,
            "spread": (ask - bid) if bid is not None and ask is not None else None,
            "volume": snap.get("volume"),
            "previous_close": snap.get("previous_close"),
            "day_change": snap.get("day_change"),
            "day_change_pct": snap.get("day_change_pct"),
            "session": snap.get("session"),
            "timestamp": snap.get("last_update") or snap.get("timestamp"),
            "freshness": snap.get("freshness"),
            "source": snap.get("source") or "alpaca",
            "feed": snap.get("feed") or "iex",
            "market_open": snap.get("session") == "REGULAR",
            "clock_availability": snap.get("clock", {}).get("availability") if isinstance(snap.get("clock"), dict) else None,
            "valid": isinstance(current, (int, float)) and not fail_closed,
            "missing": missing,
            "integrity": integrity,
            "integrity_state": snap.get("integrity_state") or integrity.get("integrity_state"),
            "integrity_fail_closed": fail_closed,
            "integrity_notes": snap.get("integrity_notes") or integrity.get("notes"),
        }

    async def get_option_contracts(
        self,
        underlying_symbol: str,
        expiration_start: Optional[str] = None,
        expiration_end: Optional[str] = None,
        option_type: Optional[str] = None,
        strike_min: Optional[float] = None,
        strike_max: Optional[float] = None,
        status: str = "active",
        limit: int = 200,
    ) -> List[OptionContract]:
        params: Dict[str, Any] = {
            "underlying_symbols": underlying_symbol,
            "status": status,
            "limit": min(limit, 1000),
        }
        if expiration_start:
            params["expiration_date_gte"] = expiration_start
        if expiration_end:
            params["expiration_date_lte"] = expiration_end
        if option_type:
            params["type"] = option_type.lower()
        if strike_min is not None:
            params["strike_price_gte"] = strike_min
        if strike_max is not None:
            params["strike_price_lte"] = strike_max
        try:
            raw = await self.client.get_option_contracts(params)
        except AlpacaRateLimitError:
            logger.error("Option contracts rate limited")
            return []
        except AlpacaError as exc:
            logger.error("Option contracts unavailable: %s", exc)
            return []
        rows = raw.get("option_contracts") or raw.get("contracts") or []
        contracts: List[OptionContract] = []
        for row in rows:
            occ = row.get("symbol") or row.get("occ_symbol")
            if not occ:
                continue
            contracts.append(
                OptionContract(
                    occ_symbol=occ,
                    underlying_symbol=row.get("underlying_symbol") or underlying_symbol,
                    option_type=(row.get("type") or row.get("option_type") or "").lower() or None,
                    strike=_opt_float(row.get("strike_price") or row.get("strike")),
                    expiration=row.get("expiration_date") or row.get("expiration"),
                    multiplier=str(row.get("multiplier")) if row.get("multiplier") is not None else None,
                    tradable=_opt_bool(row.get("tradable")),
                    status=row.get("status"),
                    open_interest=_opt_float(row.get("open_interest")),
                    close_price=_opt_float(row.get("close_price")),
                )
            )
        return contracts

    def _map_option_snapshot(self, occ: str, payload: Dict[str, Any]) -> OptionSnapshot:
        received = datetime.now(timezone.utc)
        latest_quote = payload.get("latestQuote") or payload.get("latest_quote") or {}
        latest_trade = payload.get("latestTrade") or payload.get("latest_trade") or {}
        greeks = payload.get("greeks") or {}
        ts = parse_alpaca_time(
            latest_quote.get("t")
            or latest_trade.get("t")
            or payload.get("timestamp")
        )
        freshness = evaluate_freshness(ts, max_age_seconds=settings.option_quote_max_age_seconds)
        delta = _opt_float(greeks.get("delta"))
        greeks_quality = "REAL" if any(
            _opt_float(greeks.get(k)) is not None for k in ("delta", "gamma", "theta", "vega")
        ) else DATA_UNAVAILABLE
        bid = _opt_float(latest_quote.get("bp"))
        ask = _opt_float(latest_quote.get("ap"))
        available = "AVAILABLE" if bid is not None or ask is not None or latest_trade else DATA_UNAVAILABLE
        return OptionSnapshot(
            occ_symbol=occ,
            bid=bid,
            ask=ask,
            last_price=_opt_float(latest_trade.get("p")),
            volume=_opt_float(payload.get("volume") or latest_trade.get("s")),
            implied_volatility=_opt_float(payload.get("impliedVolatility") or payload.get("implied_volatility")),
            delta=delta,
            gamma=_opt_float(greeks.get("gamma")),
            theta=_opt_float(greeks.get("theta")),
            vega=_opt_float(greeks.get("vega")),
            rho=_opt_float(greeks.get("rho")),
            timestamp=ts,
            received_at=received,
            freshness=freshness,
            greeks_quality=greeks_quality,
            availability=available,
        )

    async def get_option_snapshots(self, underlying: str, **params: Any) -> Dict[str, OptionSnapshot]:
        try:
            raw = await self.client.get_option_snapshots_for_underlying(underlying, params or None)
        except AlpacaRateLimitError:
            return {}
        except AlpacaError:
            return {}
        snapshots = raw.get("snapshots") or {}
        mapped: Dict[str, OptionSnapshot] = {}
        for occ, payload in snapshots.items():
            if isinstance(payload, dict):
                mapped[occ] = self._map_option_snapshot(occ, payload)
        return mapped

    async def get_option_snapshot(self, occ_symbol: str) -> Optional[OptionSnapshot]:
        try:
            raw = await self.client.get_option_snapshots_by_symbols([occ_symbol])
        except AlpacaError:
            return None
        snapshots = raw.get("snapshots") or {}
        payload = snapshots.get(occ_symbol)
        if not isinstance(payload, dict):
            return None
        return self._map_option_snapshot(occ_symbol, payload)
