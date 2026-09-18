"""Persistent post-trade / cycle memory using sqlite (stdlib)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import List, Optional

from app.config import BACKEND_DIR
from app.models.schemas import TradeMemoryRecord


class PostTradeMemory:
    """Stores structured cycle outcomes. Does not claim live fills for dry-run."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else BACKEND_DIR / "data" / "trade_memory.sqlite"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trade_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_id TEXT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def record(self, item: TradeMemoryRecord) -> TradeMemoryRecord:
        payload = item.model_dump(mode="json")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO trade_memory (cycle_id, timestamp, symbol, payload) VALUES (?, ?, ?, ?)",
                (
                    item.cycle_id,
                    item.timestamp.isoformat(),
                    item.symbol,
                    json.dumps(payload),
                ),
            )
            conn.commit()
        return item

    def list_records(self, symbol: Optional[str] = None, limit: int = 100) -> List[TradeMemoryRecord]:
        sql = "SELECT payload FROM trade_memory"
        params: list = []
        if symbol:
            sql += " WHERE symbol = ?"
            params.append(symbol)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [TradeMemoryRecord.model_validate_json(row["payload"]) for row in rows]
