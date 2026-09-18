"""Alpaca PAPER trading + market-data HTTP client. Live trading is blocked."""

from typing import Any, Dict, List, Optional

import httpx

from app.alpaca.exceptions import (
    AlpacaAuthError,
    AlpacaConfigError,
    AlpacaDataUnavailable,
    AlpacaError,
    AlpacaLiveTradingBlocked,
    AlpacaRateLimitError,
)
from app.config import DATA_API_URL, LIVE_API_URL, PAPER_API_URL, settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class AlpacaClient:
    """Authenticated client for the Alpaca paper trading REST API and data API."""

    def __init__(self) -> None:
        self.base_url = settings.alpaca_base_url.rstrip("/")
        self.data_url = (settings.alpaca_data_url or DATA_API_URL).rstrip("/")
        self._validate_paper_only()

    def _validate_paper_only(self) -> None:
        if not settings.alpaca_paper_trade:
            raise AlpacaLiveTradingBlocked("SECURITY: Live trading is disabled")
        if self.base_url.lower() != PAPER_API_URL:
            raise AlpacaLiveTradingBlocked("SECURITY: Only the Alpaca paper API is allowed")
        if self.base_url.lower() == LIVE_API_URL:
            raise AlpacaLiveTradingBlocked("SECURITY: Live trading is disabled")
        if self.data_url.lower() == LIVE_API_URL:
            raise AlpacaLiveTradingBlocked("SECURITY: Live trading is disabled")

    def _headers(self) -> Dict[str, str]:
        if not settings.alpaca_keys_configured():
            raise AlpacaConfigError("Alpaca API credentials are not configured")
        return {
            "APCA-API-KEY-ID": settings.alpaca_api_key.strip(),
            "APCA-API-SECRET-KEY": settings.alpaca_secret_key.strip(),
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Any:
        self._validate_paper_only()
        lowered = url.lower()
        if lowered.startswith(LIVE_API_URL) or (
            "/v2/orders" in lowered and not lowered.startswith(PAPER_API_URL)
        ):
            raise AlpacaLiveTradingBlocked("SECURITY: Live trading is disabled")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.request(
                    method, url, headers=self._headers(), params=params, json=json
                )
        except httpx.RequestError as exc:
            logger.error("Alpaca request failed: %s", type(exc).__name__)
            raise AlpacaError("Alpaca paper API request failed") from exc

        if response.status_code in (401, 403):
            raise AlpacaAuthError("Alpaca paper API authentication failed")
        if response.status_code == 404:
            raise AlpacaDataUnavailable("Alpaca resource not found")
        if response.status_code == 429:
            raise AlpacaRateLimitError("Alpaca rate limit exceeded")
        if response.status_code >= 400:
            detail = f"Alpaca endpoint returned HTTP {response.status_code}"
            try:
                body = response.json()
                message = body.get("message") or body.get("error") if isinstance(body, dict) else None
                if message:
                    detail = str(message)[:300]
            except ValueError:
                pass
            logger.error("Alpaca endpoint returned HTTP %s", response.status_code)
            raise AlpacaError(detail)

        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise AlpacaError("Alpaca returned a malformed JSON response") from exc

    async def get_account(self) -> Dict[str, Any]:
        """GET /v2/account against the paper API."""
        return await self._request("GET", f"{self.base_url}/v2/account")

    async def get_clock(self) -> Dict[str, Any]:
        return await self._request("GET", f"{self.base_url}/v2/clock")

    async def get_asset(self, symbol: str) -> Dict[str, Any]:
        return await self._request("GET", f"{self.base_url}/v2/assets/{symbol}")

    async def get_latest_stock_quote(self, symbol: str, feed: str = "iex") -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if feed:
            params["feed"] = feed
        return await self._request(
            "GET",
            f"{self.data_url}/v2/stocks/{symbol}/quotes/latest",
            params=params or None,
        )

    async def get_latest_stock_trade(self, symbol: str, feed: str = "iex") -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if feed:
            params["feed"] = feed
        return await self._request(
            "GET",
            f"{self.data_url}/v2/stocks/{symbol}/trades/latest",
            params=params or None,
        )

    async def get_stock_bars(
        self,
        symbol: str,
        timeframe: str = "1Day",
        limit: int = 20,
        start: Optional[str] = None,
        end: Optional[str] = None,
        page_token: Optional[str] = None,
        feed: str = "iex",
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"timeframe": timeframe, "limit": limit, "adjustment": "raw"}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if page_token:
            params["page_token"] = page_token
        if feed:
            params["feed"] = feed
        return await self._request(
            "GET",
            f"{self.data_url}/v2/stocks/{symbol}/bars",
            params=params,
        )

    async def get_latest_stock_quotes(self, symbols: List[str], feed: str = "iex") -> Dict[str, Any]:
        joined = ",".join(symbols)
        params: Dict[str, Any] = {"symbols": joined}
        if feed:
            params["feed"] = feed
        return await self._request("GET", f"{self.data_url}/v2/stocks/quotes/latest", params=params)

    async def get_latest_stock_trades(self, symbols: List[str], feed: str = "iex") -> Dict[str, Any]:
        joined = ",".join(symbols)
        params: Dict[str, Any] = {"symbols": joined}
        if feed:
            params["feed"] = feed
        return await self._request("GET", f"{self.data_url}/v2/stocks/trades/latest", params=params)

    async def get_stock_bars_multi(
        self,
        symbols: List[str],
        timeframe: str = "1Day",
        limit: int = 60,
        start: Optional[str] = None,
        feed: str = "iex",
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "symbols": ",".join(symbols),
            "timeframe": timeframe,
            "limit": limit,
            "adjustment": "raw",
        }
        if start:
            params["start"] = start
        if feed:
            params["feed"] = feed
        return await self._request("GET", f"{self.data_url}/v2/stocks/bars", params=params)

    async def get_option_contracts(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request(
            "GET", f"{self.base_url}/v2/options/contracts", params=params
        )

    async def get_option_snapshots_for_underlying(
        self, underlying: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        query = {"feed": "indicative", "limit": 100}
        if params:
            query.update({k: v for k, v in params.items() if v is not None})
        return await self._request(
            "GET",
            f"{self.data_url}/v1beta1/options/snapshots/{underlying}",
            params=query,
        )

    async def get_option_snapshots_by_symbols(self, symbols: List[str]) -> Dict[str, Any]:
        if not symbols:
            return {"snapshots": {}}
        joined = ",".join(symbols[:100])
        return await self._request(
            "GET",
            f"{self.data_url}/v1beta1/options/snapshots",
            params={"symbols": joined, "feed": "indicative"},
        )

    def _assert_paper_order_url(self, url: str) -> None:
        lowered = url.rstrip("/").lower()
        if not lowered.startswith(PAPER_API_URL):
            raise AlpacaLiveTradingBlocked("SECURITY: Only the Alpaca paper API is allowed")
        if lowered.startswith(LIVE_API_URL):
            raise AlpacaLiveTradingBlocked("SECURITY: Live trading is disabled")

    async def submit_paper_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/v2/orders"
        self._assert_paper_order_url(url)
        return await self._request("POST", url, json=payload)

    async def get_orders(self, status: str = "all", limit: int = 100) -> Any:
        return await self._request(
            "GET",
            f"{self.base_url}/v2/orders",
            params={"status": status, "limit": min(limit, 500), "direction": "desc"},
        )

    async def get_order(self, order_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"{self.base_url}/v2/orders/{order_id}")

    async def get_positions(self) -> Any:
        return await self._request("GET", f"{self.base_url}/v2/positions")
