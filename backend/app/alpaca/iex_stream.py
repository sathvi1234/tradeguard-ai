"""Alpaca IEX market-data WebSocket. Credentials stay on the backend."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set

from fastapi import WebSocket

from app.alpaca.freshness import parse_alpaca_time
from app.config import IEX_STREAM_URL, LIVE_API_URL, settings
from app.services.market_snapshot import DATA_FEED, DEFAULT_WATCHLIST, enrich_market_state
from app.utils.logging import get_logger

logger = get_logger(__name__)

_SECRET_KEYS = {"key", "secret", "alpaca_api_key", "alpaca_secret_key", "APCA-API-KEY-ID", "APCA-API-SECRET-KEY"}


def _public_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in payload.items() if k not in _SECRET_KEYS}


class IexStreamHub:
    """Single backend connection to Alpaca IEX; fan-out to browser sockets without credentials."""

    def __init__(self) -> None:
        self.feed = DATA_FEED
        self.url = IEX_STREAM_URL
        self.state = "DISCONNECTED"
        self.last_error: Optional[str] = None
        self.quotes: Dict[str, Dict[str, Any]] = {}
        self.symbols: Set[str] = set(DEFAULT_WATCHLIST)
        self._clients: Set[WebSocket] = set()
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._ws = None

    def status(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "feed": self.feed,
            "url": self.url,
            "symbols": sorted(self.symbols),
            "live_market_data": self.state == "LIVE",
            "live_trading": False,
            "paper_trading": True,
            "dry_run": settings.dry_run,
            "error": self.last_error,
        }

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="iex-stream")

    async def stop(self) -> None:
        self._stop.set()
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self._task = None
        self.state = "DISCONNECTED"

    async def add_client(self, websocket: WebSocket, symbols: Optional[Iterable[str]] = None) -> None:
        self._clients.add(websocket)
        extra = [s.upper() for s in (symbols or []) if s]
        if extra:
            await self.subscribe(extra)
        await websocket.send_json(_public_payload({"type": "status", **self.status()}))
        for symbol, quote in list(self.quotes.items()):
            await websocket.send_json(_public_payload({"type": "quote", **quote, "symbol": symbol}))

    def remove_client(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

    async def subscribe(self, symbols: List[str]) -> None:
        added = []
        for symbol in symbols:
            key = "".join(ch for ch in symbol.upper() if ch.isalpha() or ch == ".")
            if 1 <= len(key) <= 8 and key not in self.symbols:
                self.symbols.add(key)
                added.append(key)
        if added and self._ws is not None and self.state == "LIVE":
            await self._send({"action": "subscribe", "trades": added, "quotes": added})

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        message = _public_payload(payload)
        for client in list(self._clients):
            try:
                await asyncio.wait_for(client.send_json(message), timeout=1.0)
            except Exception:
                self._clients.discard(client)

    async def _send(self, payload: Dict[str, Any]) -> None:
        if self._ws is None:
            return
        await self._ws.send(json.dumps(payload))

    async def _run(self) -> None:
        try:
            import websockets
        except ImportError:
            self.state = "DISCONNECTED"
            self.last_error = "websockets package is not installed"
            logger.error("IEX stream unavailable: websockets package missing")
            return

        delay = 1.0
        while not self._stop.is_set():
            if LIVE_API_URL in self.url:
                self.state = "DISCONNECTED"
                self.last_error = "Live trading stream is blocked"
                return
            self.state = "RECONNECTING"
            await self.broadcast({"type": "status", **self.status()})
            try:
                async with websockets.connect(self.url, ping_interval=20, ping_timeout=20) as ws:
                    self._ws = ws
                    authenticated = await self._authenticate(ws)
                    if not authenticated:
                        self.state = "DISCONNECTED"
                        await asyncio.sleep(min(delay, 15))
                        delay = min(delay * 2, 15)
                        continue
                    symbols = sorted(self.symbols)
                    await ws.send(json.dumps({"action": "subscribe", "trades": symbols, "quotes": symbols}))
                    self.state = "LIVE"
                    self.last_error = None
                    delay = 1.0
                    await self.broadcast({"type": "status", **self.status()})
                    async for raw in ws:
                        if self._stop.is_set():
                            return
                        await self._handle_raw(raw)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.state = "RECONNECTING"
                self.last_error = type(exc).__name__
                logger.error("IEX stream reconnecting after %s", type(exc).__name__)
                await self.broadcast({"type": "status", **self.status()})
                await asyncio.sleep(min(delay, 15))
                delay = min(delay * 2, 15)
            finally:
                self._ws = None
        self.state = "DISCONNECTED"

    async def _authenticate(self, ws: Any) -> bool:
        if not settings.alpaca_keys_configured():
            self.last_error = "Alpaca credentials are not configured"
            return False
        await ws.recv()
        await ws.send(
            json.dumps(
                {
                    "action": "auth",
                    "key": settings.alpaca_api_key.strip(),
                    "secret": settings.alpaca_secret_key.strip(),
                }
            )
        )
        reply = await ws.recv()
        try:
            rows = json.loads(reply)
        except ValueError:
            self.last_error = "invalid_auth_response"
            return False
        if isinstance(rows, dict):
            rows = [rows]
        for row in rows or []:
            if isinstance(row, dict) and row.get("T") == "success" and str(row.get("msg", "")).lower() == "authenticated":
                return True
            if isinstance(row, dict) and row.get("T") == "error":
                self.last_error = "authentication_failed"
                logger.error("IEX stream authentication failed")
                return False
        self.last_error = "authentication_failed"
        return False

    async def _handle_raw(self, raw: Any) -> None:
        try:
            rows = json.loads(raw)
        except ValueError:
            return
        if isinstance(rows, dict):
            rows = [rows]
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            kind = row.get("T")
            symbol = str(row.get("S") or "").upper()
            if kind == "t" and symbol:
                ts = parse_alpaca_time(row.get("t"))
                price = row.get("p")
                size = row.get("s")
                current = self.quotes.setdefault(symbol, {"symbol": symbol, "feed": self.feed, "source": "alpaca"})
                if isinstance(price, (int, float)):
                    current["price"] = float(price)
                    current["last_trade_price"] = float(price)
                if isinstance(size, (int, float)):
                    current["last_trade_size"] = float(size)
                    current["volume"] = float(current.get("volume") or 0) + float(size)
                current["last_update"] = ts.isoformat() if ts else datetime.now(timezone.utc).isoformat()
                current["freshness"] = "FRESH"
                current["live"] = True
                current["ws_state"] = self.state
                await self.broadcast({"type": "trade", **current})
            elif kind == "q" and symbol:
                ts = parse_alpaca_time(row.get("t"))
                bid = row.get("bp")
                ask = row.get("ap")
                current = self.quotes.setdefault(symbol, {"symbol": symbol, "feed": self.feed, "source": "alpaca"})
                if isinstance(bid, (int, float)) and bid > 0:
                    current["bid"] = float(bid)
                if isinstance(ask, (int, float)) and ask > 0:
                    current["ask"] = float(ask)
                bid_v = current.get("bid")
                ask_v = current.get("ask")
                if isinstance(bid_v, (int, float)) and isinstance(ask_v, (int, float)) and bid_v > 0 and ask_v > 0:
                    current["mid"] = round((bid_v + ask_v) / 2, 6)
                    current["spread"] = round(ask_v - bid_v, 6)
                    current["spread_pct"] = round((ask_v - bid_v) / ((bid_v + ask_v) / 2), 6)
                    if current.get("price") is None:
                        current["price"] = current["mid"]
                current["last_update"] = ts.isoformat() if ts else datetime.now(timezone.utc).isoformat()
                current["freshness"] = "FRESH"
                current["live"] = True
                current["ws_state"] = self.state
                await self.broadcast({"type": "quote", **current})
            elif kind == "error":
                self.last_error = "stream_error"
                logger.error("IEX stream error message received")


_hub: Optional[IexStreamHub] = None


def get_iex_hub() -> IexStreamHub:
    global _hub
    if _hub is None:
        _hub = IexStreamHub()
    return _hub


def overlay_snapshot(item: Dict[str, Any]) -> Dict[str, Any]:
    """Merge live IEX stream fields onto a REST snapshot. Never invent prices."""
    if not isinstance(item, dict):
        return item
    hub = get_iex_hub()
    symbol = str(item.get("symbol") or "").upper()
    item["ws_state"] = hub.state
    item["feed"] = item.get("feed") or hub.feed
    item["data_freshness"] = item.get("freshness")
    streamed = hub.quotes.get(symbol) if symbol else None
    if isinstance(streamed, dict):
        for key in ("price", "bid", "ask", "mid", "spread", "spread_pct", "last_trade_price", "last_trade_size"):
            value = streamed.get(key)
            if isinstance(value, (int, float)):
                item[key] = value
        if streamed.get("last_update"):
            item["last_update"] = streamed["last_update"]
            item["freshness"] = "FRESH"
            item["data_freshness"] = "FRESH"
            item["live"] = True
            item["live_market_data"] = True
        prev = item.get("previous_close")
        price = item.get("price")
        if isinstance(prev, (int, float)) and prev > 0 and isinstance(price, (int, float)):
            item["day_change"] = round(price - prev, 4)
            item["day_change_pct"] = round((price - prev) / prev, 6)
    item["ws_state"] = hub.state
    item["feed"] = hub.feed
    return enrich_market_state(item)
