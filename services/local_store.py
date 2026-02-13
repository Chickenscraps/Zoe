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

            -- ═══════════════════════════════════════════════
            -- LOCAL-FIRST TRADING TABLES (Iron Lung Protocol)
            -- Write-through: local first, async flush to Supabase
            -- ═══════════════════════════════════════════════

            CREATE TABLE IF NOT EXISTS local_orders (
                order_id TEXT PRIMARY KEY,
                client_order_id TEXT UNIQUE,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT NOT NULL DEFAULT 'limit',
                qty REAL,
                notional REAL,
                limit_price REAL,
                status TEXT NOT NULL DEFAULT 'pending',
                filled_qty REAL DEFAULT 0,
                filled_avg_price REAL DEFAULT 0,
                fees REAL DEFAULT 0,
                broker_order_id TEXT,
                idempotency_key TEXT UNIQUE,
                trace_id TEXT,
                mode TEXT NOT NULL,
                raw_response TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                flushed INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_local_orders_mode_status
                ON local_orders (mode, status);

            CREATE INDEX IF NOT EXISTS idx_local_orders_unflushed
                ON local_orders (flushed)
                WHERE flushed = 0;

            CREATE TABLE IF NOT EXISTS local_positions (
                position_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL DEFAULT 'long',
                entry_price REAL NOT NULL,
                size_usd REAL NOT NULL,
                qty REAL NOT NULL DEFAULT 0,
                tp_price REAL,
                sl_price REAL,
                exit_price REAL,
                exit_time TEXT,
                pnl_usd REAL,
                status TEXT NOT NULL DEFAULT 'open',
                entry_order_id TEXT,
                exit_order_id TEXT,
                signal_strength REAL,
                regime TEXT,
                mode TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                flushed INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_local_positions_mode_status
                ON local_positions (mode, status);

            CREATE INDEX IF NOT EXISTS idx_local_positions_unflushed
                ON local_positions (flushed)
                WHERE flushed = 0;

            CREATE TABLE IF NOT EXISTS local_daily_notional (
                day TEXT NOT NULL,
                mode TEXT NOT NULL,
                notional_used REAL NOT NULL DEFAULT 0,
                notional_limit REAL NOT NULL DEFAULT 50,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (day, mode)
            );

            CREATE TABLE IF NOT EXISTS local_ticker_cache (
                symbol TEXT NOT NULL,
                bid REAL,
                ask REAL,
                mid REAL,
                spread_pct REAL,
                ts TEXT NOT NULL,
                PRIMARY KEY (symbol)
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

    # ═══════════════════════════════════════════════════════
    # LOCAL-FIRST ORDER METHODS
    # ═══════════════════════════════════════════════════════

    def insert_order(self, order: dict[str, Any]) -> None:
        """Insert an order into local store (write-through first step)."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT OR REPLACE INTO local_orders
               (order_id, client_order_id, symbol, side, order_type,
                qty, notional, limit_price, status, filled_qty,
                filled_avg_price, fees, broker_order_id, idempotency_key,
                trace_id, mode, raw_response, created_at, updated_at, flushed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (
                order.get("order_id", str(uuid.uuid4())),
                order.get("client_order_id"),
                order["symbol"],
                order["side"],
                order.get("order_type", "limit"),
                order.get("qty"),
                order.get("notional"),
                order.get("limit_price"),
                order.get("status", "pending"),
                order.get("filled_qty", 0),
                order.get("filled_avg_price", 0),
                order.get("fees", 0),
                order.get("broker_order_id"),
                order.get("idempotency_key"),
                order.get("trace_id"),
                order["mode"],
                order.get("raw_response"),
                order.get("created_at", now),
                now,
            ),
        )
        self.conn.commit()

    def update_order_status(
        self, order_id: str, status: str, **kwargs: Any
    ) -> None:
        """Update an order's status and optional fields."""
        now = datetime.now(timezone.utc).isoformat()
        sets = ["status = ?", "updated_at = ?", "flushed = 0"]
        vals: list[Any] = [status, now]

        for key in ("filled_qty", "filled_avg_price", "fees", "broker_order_id", "raw_response"):
            if key in kwargs:
                sets.append(f"{key} = ?")
                vals.append(kwargs[key])

        vals.append(order_id)
        self.conn.execute(
            f"UPDATE local_orders SET {', '.join(sets)} WHERE order_id = ?",
            vals,
        )
        self.conn.commit()

    def get_open_orders(self, mode: str) -> list[dict[str, Any]]:
        """Get all open/pending orders for a mode."""
        rows = self.conn.execute(
            """SELECT * FROM local_orders
               WHERE mode = ? AND status IN ('pending', 'open', 'queued')
               ORDER BY created_at DESC""",
            (mode,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        """Get a single order by ID."""
        row = self.conn.execute(
            "SELECT * FROM local_orders WHERE order_id = ?", (order_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_unflushed_orders(self, limit: int = 500) -> list[dict[str, Any]]:
        """Get orders that haven't been flushed to Supabase."""
        rows = self.conn.execute(
            """SELECT * FROM local_orders
               WHERE flushed = 0
               ORDER BY created_at ASC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_orders_flushed(self, order_ids: list[str]) -> None:
        """Mark orders as flushed after successful Supabase write."""
        if not order_ids:
            return
        placeholders = ",".join(["?"] * len(order_ids))
        self.conn.execute(
            f"UPDATE local_orders SET flushed = 1 WHERE order_id IN ({placeholders})",
            order_ids,
        )
        self.conn.commit()

    # ═══════════════════════════════════════════════════════
    # LOCAL-FIRST POSITION METHODS
    # ═══════════════════════════════════════════════════════

    def insert_position(self, position: dict[str, Any]) -> None:
        """Insert a position into local store."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT OR REPLACE INTO local_positions
               (position_id, symbol, side, entry_price, size_usd, qty,
                tp_price, sl_price, exit_price, exit_time, pnl_usd,
                status, entry_order_id, exit_order_id, signal_strength,
                regime, mode, created_at, updated_at, flushed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (
                position.get("position_id", str(uuid.uuid4())),
                position["symbol"],
                position.get("side", "long"),
                position["entry_price"],
                position["size_usd"],
                position.get("qty", position["size_usd"] / position["entry_price"] if position["entry_price"] > 0 else 0),
                position.get("tp_price"),
                position.get("sl_price"),
                position.get("exit_price"),
                position.get("exit_time"),
                position.get("pnl_usd"),
                position.get("status", "open"),
                position.get("entry_order_id"),
                position.get("exit_order_id"),
                position.get("signal_strength"),
                position.get("regime"),
                position["mode"],
                position.get("created_at", now),
                now,
            ),
        )
        self.conn.commit()

    def update_position(self, position_id: str, updates: dict[str, Any]) -> None:
        """Update a position with given fields."""
        now = datetime.now(timezone.utc).isoformat()
        sets = ["updated_at = ?", "flushed = 0"]
        vals: list[Any] = [now]

        allowed = (
            "exit_price", "exit_time", "pnl_usd", "status",
            "exit_order_id", "tp_price", "sl_price",
        )
        for key in allowed:
            if key in updates:
                sets.append(f"{key} = ?")
                vals.append(updates[key])

        vals.append(position_id)
        self.conn.execute(
            f"UPDATE local_positions SET {', '.join(sets)} WHERE position_id = ?",
            vals,
        )
        self.conn.commit()

    def get_open_positions(self, mode: str) -> list[dict[str, Any]]:
        """Get all open positions for a mode."""
        rows = self.conn.execute(
            """SELECT * FROM local_positions
               WHERE mode = ? AND status = 'open'
               ORDER BY created_at DESC""",
            (mode,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_closed_positions(self, mode: str, limit: int = 50) -> list[dict[str, Any]]:
        """Get recently closed positions for a mode."""
        rows = self.conn.execute(
            """SELECT * FROM local_positions
               WHERE mode = ? AND status != 'open'
               ORDER BY updated_at DESC
               LIMIT ?""",
            (mode, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_unflushed_positions(self, limit: int = 500) -> list[dict[str, Any]]:
        """Get positions that haven't been flushed to Supabase."""
        rows = self.conn.execute(
            """SELECT * FROM local_positions
               WHERE flushed = 0
               ORDER BY created_at ASC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_positions_flushed(self, position_ids: list[str]) -> None:
        """Mark positions as flushed after successful Supabase write."""
        if not position_ids:
            return
        placeholders = ",".join(["?"] * len(position_ids))
        self.conn.execute(
            f"UPDATE local_positions SET flushed = 1 WHERE position_id IN ({placeholders})",
            position_ids,
        )
        self.conn.commit()

    # ═══════════════════════════════════════════════════════
    # LOCAL DAILY NOTIONAL TRACKING
    # ═══════════════════════════════════════════════════════

    def get_daily_notional(self, mode: str, day: str | None = None) -> dict[str, Any]:
        """Get daily notional usage. day defaults to today."""
        if day is None:
            day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = self.conn.execute(
            "SELECT * FROM local_daily_notional WHERE mode = ? AND day = ?",
            (mode, day),
        ).fetchone()
        if row:
            return dict(row)
        return {"day": day, "mode": mode, "notional_used": 0.0, "notional_limit": 50.0}

    def add_daily_notional(self, mode: str, amount: float, limit: float = 50.0) -> dict[str, Any]:
        """Add to daily notional usage. Returns updated record."""
        now = datetime.now(timezone.utc)
        day = now.strftime("%Y-%m-%d")
        self.conn.execute(
            """INSERT INTO local_daily_notional (day, mode, notional_used, notional_limit, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(day, mode) DO UPDATE SET
                   notional_used = notional_used + excluded.notional_used,
                   updated_at = excluded.updated_at""",
            (day, mode, amount, limit, now.isoformat()),
        )
        self.conn.commit()
        return self.get_daily_notional(mode, day)

    # ═══════════════════════════════════════════════════════
    # LOCAL TICKER CACHE (for MtM pricing)
    # ═══════════════════════════════════════════════════════

    def update_ticker(
        self, symbol: str, bid: float, ask: float
    ) -> None:
        """Update cached BBO for a symbol."""
        mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0.0
        spread_pct = ((ask - bid) / mid * 100) if mid > 0 else 0.0
        ts = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT OR REPLACE INTO local_ticker_cache
               (symbol, bid, ask, mid, spread_pct, ts)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (symbol, bid, ask, mid, spread_pct, ts),
        )
        self.conn.commit()

    def get_ticker(self, symbol: str) -> dict[str, Any] | None:
        """Get cached BBO for a symbol."""
        row = self.conn.execute(
            "SELECT * FROM local_ticker_cache WHERE symbol = ?", (symbol,)
        ).fetchone()
        return dict(row) if row else None

    def get_all_tickers(self) -> dict[str, dict[str, Any]]:
        """Get all cached tickers."""
        rows = self.conn.execute("SELECT * FROM local_ticker_cache").fetchall()
        return {r["symbol"]: dict(r) for r in rows}

    def close(self) -> None:
        self.conn.close()
