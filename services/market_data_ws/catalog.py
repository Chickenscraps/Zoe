"""Market Catalog — discover and cache tradable pairs from Kraken."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from integrations.kraken_client.symbols import populate_from_asset_pairs

logger = logging.getLogger(__name__)


class MarketCatalog:
    """Discovers pairs from Kraken AssetPairs, writes to market_catalog table."""

    def __init__(self, exchange_client: Any, supabase: Any, quote_filter: str = "USD"):
        self.exchange = exchange_client
        self.sb = supabase
        self.quote_filter = quote_filter
        self._pairs: dict[str, dict] = {}  # symbol -> pair info

    async def refresh(self) -> int:
        """Fetch all tradable pairs from Kraken and upsert to market_catalog.

        Returns number of pairs written.
        """
        raw_pairs = await self.exchange.get_trading_pairs()
        if not raw_pairs:
            logger.warning("No trading pairs returned from exchange")
            return 0

        # Populate the symbol normalization cache
        populate_from_asset_pairs(raw_pairs)

        rows: list[dict] = []
        now = datetime.now(timezone.utc).isoformat()

        for kraken_pair, info in raw_pairs.items():
            parsed = self._parse_pair(kraken_pair, info)
            if parsed is None:
                continue

            # Filter to requested quote currency
            if parsed["quote"] != self.quote_filter:
                continue

            rows.append({
                "symbol": parsed["symbol"],
                "exchange_symbol": kraken_pair,
                "ws_symbol": parsed.get("ws_symbol", ""),
                "base": parsed["base"],
                "quote": parsed["quote"],
                "exchange": "kraken",
                "status": "active",
                "min_qty": parsed.get("min_qty", 0),
                "lot_size": parsed.get("lot_size", 0),
                "tick_size": parsed.get("tick_size", 0),
                "fee_maker_pct": parsed.get("fee_maker", 0.16),
                "fee_taker_pct": parsed.get("fee_taker", 0.26),
                "ordermin": parsed.get("ordermin", 0),
                "metadata": {
                    "altname": info.get("altname", ""),
                    "pair_decimals": info.get("pair_decimals"),
                    "lot_decimals": info.get("lot_decimals"),
                },
                "updated_at": now,
            })

            self._pairs[parsed["symbol"]] = parsed

        if not rows:
            logger.warning("No USD pairs found in catalog")
            return 0

        # Batch upsert to Supabase
        try:
            # Upsert in chunks of 100
            chunk_size = 100
            for i in range(0, len(rows), chunk_size):
                chunk = rows[i : i + chunk_size]
                self.sb.table("market_catalog").upsert(
                    chunk, on_conflict="symbol"
                ).execute()

            logger.info("Market catalog refreshed: %d %s pairs", len(rows), self.quote_filter)
        except Exception as e:
            logger.error("Market catalog upsert failed: %s", e)
            return 0

        return len(rows)

    def _parse_pair(self, kraken_pair: str, info: dict) -> dict | None:
        """Parse a Kraken AssetPairs entry into our catalog format."""
        base_raw = info.get("base", "")
        quote_raw = info.get("quote", "")
        wsname = info.get("wsname", "")

        if not base_raw or not quote_raw:
            return None

        # Normalize base/quote
        base = self._normalize_asset(base_raw)
        quote = self._normalize_asset(quote_raw)

        if not base or not quote:
            return None

        symbol = f"{base}-{quote}"

        # WS v2 format (standard names)
        ws_symbol = ""
        if wsname:
            ws_parts = wsname.split("/")
            if len(ws_parts) == 2:
                ws_base = _WSV1_TO_V2.get(ws_parts[0], ws_parts[0])
                ws_symbol = f"{ws_base}/{ws_parts[1]}"

        return {
            "symbol": symbol,
            "base": base,
            "quote": quote,
            "ws_symbol": ws_symbol,
            "min_qty": float(info.get("ordermin", 0)),
            "lot_size": float(info.get("lot_multiplier", 1)),
            "tick_size": 10 ** -int(info.get("pair_decimals", 8)),
            "ordermin": float(info.get("ordermin", 0)),
        }

    @staticmethod
    def _normalize_asset(raw: str) -> str:
        """Normalize Kraken asset name to standard ticker."""
        known = {"XXBT": "BTC", "XXDG": "DOGE", "XBT": "BTC", "XDG": "DOGE"}
        if raw in known:
            return known[raw]
        if len(raw) == 4 and raw.startswith("X") and raw[1:].isalpha():
            cleaned = raw[1:]
            return known.get(cleaned, cleaned)
        if len(raw) == 4 and raw.startswith("Z") and raw[1:].isalpha():
            return raw[1:]
        return known.get(raw, raw)

    def get_all_symbols(self) -> list[str]:
        """Return all cached internal symbols."""
        return list(self._pairs.keys())

    def get_ws_symbols(self) -> list[str]:
        """Return all WS v2 symbols for subscription."""
        return [p["ws_symbol"] for p in self._pairs.values() if p.get("ws_symbol")]

    def get_pair_info(self, symbol: str) -> dict | None:
        """Get catalog info for a specific symbol."""
        return self._pairs.get(symbol)


# WS v1 legacy -> v2 standard names
_WSV1_TO_V2: dict[str, str] = {
    "XBT": "BTC",
    "XDG": "DOGE",
}
