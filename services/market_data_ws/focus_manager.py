"""Focus Manager — two-tier universe management.

Focus universe (5-50 pairs): user favorites + active positions + movers
  - WS ticker, coalesced flush every 1 second
Scout universe (remaining pairs): broad market surveillance
  - WS ticker, coalesced flush every 30 seconds
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .config import MarketDataConfig

logger = logging.getLogger(__name__)


class FocusManager:
    """Manages which symbols are in focus vs scout universe."""

    def __init__(self, config: MarketDataConfig, supabase: Any | None = None):
        self.config = config
        self.sb = supabase
        self._focus: set[str] = set(config.default_focus)
        self._all_symbols: set[str] = set()

    def set_all_symbols(self, symbols: list[str]) -> None:
        """Set the full universe of available symbols."""
        self._all_symbols = set(symbols)
        logger.info("Universe set: %d total symbols", len(self._all_symbols))

    @property
    def focus_symbols(self) -> set[str]:
        """Symbols in the focus universe."""
        return self._focus & self._all_symbols

    @property
    def scout_symbols(self) -> set[str]:
        """Symbols in the scout universe (everything not in focus)."""
        return self._all_symbols - self._focus

    def promote(self, symbol: str, reason: str = "mover", ttl_minutes: int | None = None) -> None:
        """Promote a symbol to focus."""
        if symbol not in self._all_symbols:
            return
        was_new = symbol not in self._focus
        self._focus.add(symbol)
        if was_new:
            logger.info("FOCUS PROMOTE: %s (reason=%s)", symbol, reason)

            # Persist to market_focus_config
            if self.sb is not None:
                try:
                    row: dict[str, Any] = {
                        "symbol": symbol,
                        "reason": reason,
                        "promoted_at": datetime.now(timezone.utc).isoformat(),
                    }
                    if ttl_minutes is not None:
                        from datetime import timedelta
                        expires = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
                        row["expires_at"] = expires.isoformat()
                    self.sb.table("market_focus_config").upsert(
                        row, on_conflict="symbol"
                    ).execute()
                except Exception as e:
                    logger.warning("Focus config write failed for %s: %s", symbol, e)

    def demote(self, symbol: str) -> None:
        """Remove a symbol from focus (unless it's a default)."""
        if symbol in self.config.default_focus:
            return  # Never demote defaults
        self._focus.discard(symbol)
        logger.info("FOCUS DEMOTE: %s", symbol)

        if self.sb is not None:
            try:
                self.sb.table("market_focus_config").delete().eq(
                    "symbol", symbol
                ).execute()
            except Exception:
                pass

    def expire_stale_movers(self) -> int:
        """Demote movers whose TTL has expired. Returns count demoted."""
        if self.sb is None:
            return 0

        now = datetime.now(timezone.utc).isoformat()
        demoted = 0

        try:
            resp = self.sb.table("market_focus_config").select("symbol").eq(
                "reason", "mover"
            ).lt("expires_at", now).execute()

            for row in resp.data or []:
                self.demote(row["symbol"])
                demoted += 1
        except Exception as e:
            logger.warning("Expire stale movers failed: %s", e)

        return demoted

    async def load_from_db(self) -> None:
        """Load focus config from Supabase on startup."""
        if self.sb is None:
            return

        try:
            resp = self.sb.table("market_focus_config").select("symbol, reason, expires_at").execute()
            now = datetime.now(timezone.utc)

            for row in resp.data or []:
                symbol = row["symbol"]
                expires = row.get("expires_at")

                # Skip expired movers
                if expires:
                    try:
                        exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                        if exp_dt < now:
                            continue
                    except (ValueError, TypeError):
                        pass

                self._focus.add(symbol)

            logger.info("Focus loaded from DB: %d symbols", len(self._focus))
        except Exception as e:
            logger.warning("Focus config load failed: %s", e)
