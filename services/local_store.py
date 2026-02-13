"""
Local-First Event Store — SQLite WAL for high-frequency local reads
with periodic batch flush to Supabase.

Usage:
    store = LocalEventStore("data/local_events.db")
    store.insert_event(mode="live", source="broker", type="TRADE",
                       subtype="BUY_FILLED", symbol="BTC-USD",
                       body="Filled 0.001 BTC @ 66000")
    unflushed = store.get_unflushed(limit=500)
    store.mark_flushed([e["id"] for e in unflushed])
"""
from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any


class LocalEventStore:
    """SQLite WAL event store for local-first architecture."""

    def __init__(self, db_path: str = "data/local_events.db") -> None:
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
        self._seq_cache: dict[str, int] = {}

    def _init_db(self) -> None:
        """Create tables and set WAL mode."""
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA wal_autocheckpoint=1000")

        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS local_events (
                id TEXT PRIMARY KEY,
                mode TEXT NOT NULL CHECK (mode IN ('paper', 'live')),
                ts TEXT NOT NULL,
                seq INTEGER NOT NULL,
                source TEXT NOT NULL,
                type TEXT NOT NULL,
                subtype TEXT NOT NULL,
                symbol TEXT,
                severity TEXT NOT NULL DEFAULT 'info',
                body TEXT NOT NULL,
                meta_json TEXT DEFAULT '{}',
                idempotency_key TEXT UNIQUE,
                flushed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_local_events_unflushed
                ON local_events (flushed, seq ASC)
                WHERE flushed = 0;

            CREATE INDEX IF NOT EXISTS idx_local_events_mode_seq
                ON local_events (mode, seq DESC);

            CREATE TABLE IF NOT EXISTS local_flush_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL DEFAULT (datetime('now')),
                mode TEXT NOT NULL,
                count INTEGER NOT NULL,
                last_seq INTEGER NOT NULL,
                status TEXT NOT NULL,
                error TEXT
            );

            CREATE TABLE IF NOT EXISTS local_state_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode TEXT NOT NULL,
                ts TEXT NOT NULL DEFAULT (datetime('now')),
                state_json TEXT NOT NULL
            );
        """)
        self.conn.commit()

    def _next_seq(self, mode: str) -> int:
        """Get next monotonic sequence number for a mode."""
        if mode not in self._seq_cache:
            row = self.conn.execute(
                "SELECT MAX(seq) FROM local_events WHERE mode = ?", (mode,)
            ).fetchone()
            self._seq_cache[mode] = (row[0] or 0)
        self._seq_cache[mode] += 1
        return self._seq_cache[mode]

    def insert_event(
        self,
        *,
        mode: str,
        source: str,
        type: str,
        subtype: str,
        body: str,
        symbol: str | None = None,
        severity: str = "info",
        meta: dict[str, Any] | None = None,
        trace_id: str | None = None,
        config_version: int | None = None,
    ) -> dict[str, Any]:
        """Insert an event into the local store. Returns the event dict."""
        import json

        event_id = str(uuid.uuid4())
        seq = self._next_seq(mode)
        ts = datetime.now(timezone.utc).isoformat()
        idem_key = f"{mode}:{source}:{subtype}:{symbol or ''}:{ts}:{seq}"

        meta_dict = meta or {}
        if trace_id:
            meta_dict["trace_id"] = trace_id
        if config_version is not None:
            meta_dict["config_version"] = config_version

        self.conn.execute(
            """INSERT INTO local_events
               (id, mode, ts, seq, source, type, subtype, symbol, severity, body, meta_json, idempotency_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_id, mode, ts, seq, source, type, subtype, symbol,
             severity, body, json.dumps(meta_dict), idem_key),
        )
        self.conn.commit()

        return {
            "id": event_id,
            "mode": mode,
            "ts": ts,
            "seq": seq,
            "source": source,
            "type": type,
            "subtype": subtype,
            "symbol": symbol,
            "severity": severity,
            "body": body,
            "meta": meta_dict,
            "idempotency_key": idem_key,
        }

    def get_unflushed(self, limit: int = 500) -> list[dict[str, Any]]:
        """Get unflushed events ordered by seq ascending."""
        import json

        rows = self.conn.execute(
            """SELECT * FROM local_events
               WHERE flushed = 0
               ORDER BY seq ASC
               LIMIT ?""",
            (limit,),
        ).fetchall()

        return [
            {
                "id": r["id"],
                "mode": r["mode"],
                "ts": r["ts"],
                "seq": r["seq"],
                "source": r["source"],
                "type": r["type"],
                "subtype": r["subtype"],
                "symbol": r["symbol"],
                "severity": r["severity"],
                "body": r["body"],
                "meta": json.loads(r["meta_json"]) if r["meta_json"] else {},
                "idempotency_key": r["idempotency_key"],
            }
            for r in rows
        ]

    def mark_flushed(self, event_ids: list[str]) -> None:
        """Mark events as flushed after successful Supabase upsert."""
        if not event_ids:
            return
        placeholders = ",".join(["?"] * len(event_ids))
        self.conn.execute(
            f"UPDATE local_events SET flushed = 1 WHERE id IN ({placeholders})",
            event_ids,
        )
        self.conn.commit()

    def log_flush(self, mode: str, count: int, last_seq: int, status: str, error: str | None = None) -> None:
        """Record a flush attempt in the log."""
        self.conn.execute(
            """INSERT INTO local_flush_log (mode, count, last_seq, status, error)
               VALUES (?, ?, ?, ?, ?)""",
            (mode, count, last_seq, status, error),
        )
        self.conn.commit()

    def get_events_since(self, mode: str, since_seq: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        """Get events for dashboard local-live feed."""
        import json

        rows = self.conn.execute(
            """SELECT * FROM local_events
               WHERE mode = ? AND seq > ?
               ORDER BY seq DESC
               LIMIT ?""",
            (mode, since_seq, limit),
        ).fetchall()

        return [
            {
                "id": r["id"],
                "mode": r["mode"],
                "ts": r["ts"],
                "seq": r["seq"],
                "source": r["source"],
                "type": r["type"],
                "subtype": r["subtype"],
                "symbol": r["symbol"],
                "severity": r["severity"],
                "body": r["body"],
                "meta": json.loads(r["meta_json"]) if r["meta_json"] else {},
            }
            for r in rows
        ]

    def get_stats(self, mode: str) -> dict[str, Any]:
        """Get store statistics for health monitoring."""
        total = self.conn.execute(
            "SELECT COUNT(*) FROM local_events WHERE mode = ?", (mode,)
        ).fetchone()[0]
        unflushed = self.conn.execute(
            "SELECT COUNT(*) FROM local_events WHERE mode = ? AND flushed = 0", (mode,)
        ).fetchone()[0]
        last_seq = self.conn.execute(
            "SELECT MAX(seq) FROM local_events WHERE mode = ?", (mode,)
        ).fetchone()[0] or 0

        return {
            "total_events": total,
            "unflushed_events": unflushed,
            "last_seq": last_seq,
            "flushed_pct": round((total - unflushed) / max(total, 1) * 100, 1),
        }

    def save_state_snapshot(self, mode: str, state: dict[str, Any]) -> None:
        """Save periodic state snapshot for crash recovery."""
        import json
        self.conn.execute(
            "INSERT INTO local_state_snapshots (mode, state_json) VALUES (?, ?)",
            (mode, json.dumps(state)),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
