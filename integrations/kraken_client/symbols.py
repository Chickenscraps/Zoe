"""Symbol normalization between internal format (BTC-USD) and Kraken format.

Kraken uses several conventions:
- REST API: XXBTZUSD, XETHZUSD (X-prefix for crypto, Z-prefix for fiat)
- WS v1 (wsname field): XBT/USD, XDG/USD (legacy names)
- WS v2: BTC/USD, DOGE/USD (standard names — NOT XBT!)

We build the mapping dynamically from AssetPairs response at startup,
with a fallback hardcoded map for known exceptions.

IMPORTANT: WS v2 uses standard ticker names (BTC, DOGE, ETH) not the
legacy Kraken names (XBT, XDG). The wsname field in AssetPairs returns
v1 format, so we must convert XBT→BTC etc. for v2 subscriptions.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Known Kraken symbol exceptions where their name differs from standard
_KRAKEN_TO_STANDARD: dict[str, str] = {
    "XBT": "BTC",
    "XDG": "DOGE",
    "XXBT": "BTC",
    "XXDG": "DOGE",
}

_STANDARD_TO_KRAKEN_REST: dict[str, str] = {
    "BTC": "XBT",
    "DOGE": "XDG",
}

# WS v1 legacy names that need converting for v2
_WSV1_TO_STANDARD: dict[str, str] = {
    "XBT": "BTC",
    "XDG": "DOGE",
}

# Dynamic mapping populated from AssetPairs response
_pair_cache: dict[str, str] = {}  # "BTC-USD" -> "XXBTZUSD"
_reverse_cache: dict[str, str] = {}  # "XXBTZUSD" -> "BTC-USD"
_ws_pair_cache: dict[str, str] = {}  # "BTC-USD" -> "BTC/USD" (v2 format!)
_ws_reverse_cache: dict[str, str] = {}  # "BTC/USD" -> "BTC-USD"


def populate_from_asset_pairs(pairs_response: dict) -> int:
    """Populate symbol caches from Kraken AssetPairs API response.

    Args:
        pairs_response: The 'result' dict from /0/public/AssetPairs

    Returns:
        Number of pairs cached.
    """
    count = 0
    for kraken_pair, info in pairs_response.items():
        base = info.get("base", "")
        quote = info.get("quote", "")
        wsname = info.get("wsname", "")  # e.g. "XBT/USD"

        # Normalize base: strip X prefix for crypto, map known exceptions
        std_base = _normalize_asset(base)
        std_quote = _normalize_asset(quote)

        if not std_base or not std_quote:
            continue

        internal = f"{std_base}-{std_quote}"

        _pair_cache[internal] = kraken_pair
        _reverse_cache[kraken_pair] = internal

        if wsname:
            # Convert v1 wsname (XBT/USD) to v2 format (BTC/USD)
            ws_v2 = _convert_wsname_to_v2(wsname)
            _ws_pair_cache[internal] = ws_v2
            _ws_reverse_cache[ws_v2] = internal
            # Also cache v1 name for reverse lookups
            if ws_v2 != wsname:
                _ws_reverse_cache[wsname] = internal

        # Also map the altname if available
        altname = info.get("altname", "")
        if altname and altname != kraken_pair:
            _reverse_cache[altname] = internal

        count += 1

    logger.info("Symbol cache populated: %d pairs", count)
    return count


def _convert_wsname_to_v2(wsname: str) -> str:
    """Convert a v1 wsname (XBT/USD) to v2 format (BTC/USD).

    Kraken WS v2 uses standard names: BTC, DOGE, ETH, etc.
    The AssetPairs wsname field still uses v1 names: XBT, XDG, etc.
    """
    if "/" not in wsname:
        return wsname
    base, quote = wsname.split("/", 1)
    v2_base = _WSV1_TO_STANDARD.get(base, base)
    return f"{v2_base}/{quote}"


def _normalize_asset(raw: str) -> str:
    """Normalize a Kraken asset name to standard ticker.

    Kraken uses: XXBT, XETH, ZUSD, ZEUR, SOL, DOT, etc.
    We want: BTC, ETH, USD, EUR, SOL, DOT, etc.
    """
    # Check known exceptions first
    if raw in _KRAKEN_TO_STANDARD:
        return _KRAKEN_TO_STANDARD[raw]

    # Strip X prefix for crypto (XETH -> ETH) if length > 3
    if len(raw) == 4 and raw.startswith("X") and raw[1:].isalpha():
        cleaned = raw[1:]
        return _KRAKEN_TO_STANDARD.get(cleaned, cleaned)

    # Strip Z prefix for fiat (ZUSD -> USD) if length > 3
    if len(raw) == 4 and raw.startswith("Z") and raw[1:].isalpha():
        return raw[1:]

    # Already standard (SOL, DOT, AVAX, etc.)
    return _KRAKEN_TO_STANDARD.get(raw, raw)


def to_kraken(symbol: str, for_ws: bool = False) -> str:
    """Convert internal symbol (BTC-USD) to Kraken format.

    Args:
        symbol: Internal format like "BTC-USD"
        for_ws: If True, return WS format (XBT/USD), else REST format (XXBTZUSD)
    """
    if for_ws:
        cached = _ws_pair_cache.get(symbol)
        if cached:
            return cached

    cached = _pair_cache.get(symbol)
    if cached:
        if for_ws:
            # Convert REST to WS format: try wsname from our cache
            return _ws_pair_cache.get(symbol, cached)
        return cached

    # Fallback: manual construction
    parts = symbol.split("-")
    if len(parts) != 2:
        logger.warning("Cannot convert symbol %s to Kraken format", symbol)
        return symbol

    base, quote = parts

    if for_ws:
        # WS v2 uses standard names (BTC, DOGE, not XBT, XDG)
        return f"{base}/{quote}"
    else:
        # REST uses legacy names (XBT, XDG)
        kraken_base = _STANDARD_TO_KRAKEN_REST.get(base, base)
        return f"{kraken_base}{quote}"


def from_kraken(symbol: str) -> str:
    """Convert Kraken symbol to internal format (BTC-USD).

    Accepts both REST (XXBTZUSD) and WS (XBT/USD) formats.
    """
    # Check caches first
    cached = _reverse_cache.get(symbol)
    if cached:
        return cached

    cached = _ws_reverse_cache.get(symbol)
    if cached:
        return cached

    # WS format: XBT/USD -> BTC-USD
    if "/" in symbol:
        base, quote = symbol.split("/", 1)
        std_base = _KRAKEN_TO_STANDARD.get(base, base)
        return f"{std_base}-{quote}"

    # REST format fallback: try to find USD suffix
    for suffix in ("ZUSD", "USD"):
        if symbol.endswith(suffix):
            raw_base = symbol[: -len(suffix)]
            std_base = _normalize_asset(raw_base)
            return f"{std_base}-USD"

    logger.warning("Cannot convert Kraken symbol %s to internal format", symbol)
    return symbol


def get_ws_symbol(symbol: str) -> str:
    """Convenience: get WS-format symbol for subscription."""
    return to_kraken(symbol, for_ws=True)


def get_all_internal_symbols() -> list[str]:
    """Return all known internal symbols from the cache."""
    return list(_pair_cache.keys())


def get_pair_info() -> dict[str, str]:
    """Return the full internal -> REST mapping."""
    return dict(_pair_cache)
