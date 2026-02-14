"""Bidirectional symbol normalization between internal format and Kraken WS v2 format.

Internal format: "BTC-USD" (dash-separated, used throughout existing codebase)
Kraken format:   "BTC/USD" (slash-separated, used by Kraken WS v2)
Kraken legacy:   "XXBTZUSD" (X-prefixed, used by some REST endpoints)

Kraken uses "XBT" internally for Bitcoin but WS v2 uses "BTC".
"""

from __future__ import annotations

# Kraken-specific asset aliases (WS v2 uses friendly names, REST may use legacy)
_KRAKEN_TO_FRIENDLY: dict[str, str] = {
    "XBT": "BTC",
    "XDG": "DOGE",
}
_FRIENDLY_TO_KRAKEN: dict[str, str] = {v: k for k, v in _KRAKEN_TO_FRIENDLY.items()}


def to_kraken(internal_symbol: str) -> str:
    """Convert internal format to Kraken WS v2 format.

    >>> to_kraken("BTC-USD")
    'BTC/USD'
    >>> to_kraken("ETH-USD")
    'ETH/USD'
    >>> to_kraken("DOGE-USDT")
    'DOGE/USDT'
    """
    parts = internal_symbol.strip().upper().split("-")
    if len(parts) != 2:
        raise ValueError(f"Invalid internal symbol format: {internal_symbol!r} (expected BASE-QUOTE)")
    return f"{parts[0]}/{parts[1]}"


def to_internal(kraken_symbol: str) -> str:
    """Convert Kraken WS v2 format to internal format.

    >>> to_internal("BTC/USD")
    'BTC-USD'
    >>> to_internal("ETH/USD")
    'ETH-USD'
    """
    parts = kraken_symbol.strip().upper().split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid Kraken symbol format: {kraken_symbol!r} (expected BASE/QUOTE)")
    base = _KRAKEN_TO_FRIENDLY.get(parts[0], parts[0])
    quote = _KRAKEN_TO_FRIENDLY.get(parts[1], parts[1])
    return f"{base}-{quote}"


def normalize_kraken_asset(asset: str) -> str:
    """Normalize a Kraken asset code to friendly name.

    >>> normalize_kraken_asset("XBT")
    'BTC'
    >>> normalize_kraken_asset("XDG")
    'DOGE'
    >>> normalize_kraken_asset("ETH")
    'ETH'
    >>> normalize_kraken_asset("ZUSD")
    'USD'
    """
    upper = asset.strip().upper()
    # Strip Z/X prefix used in Kraken legacy REST (e.g. ZUSD -> USD, XXBT -> XBT)
    if len(upper) == 4 and upper[0] in ("Z", "X") and upper[1:] not in _KRAKEN_TO_FRIENDLY:
        stripped = upper[1:]
        return _KRAKEN_TO_FRIENDLY.get(stripped, stripped)
    return _KRAKEN_TO_FRIENDLY.get(upper, upper)


def is_usd_or_stablecoin_quoted(symbol: str) -> bool:
    """Check if a Kraken symbol is quoted in USD, USDT, or USDC.

    Works with both internal ("BTC-USD") and Kraken ("BTC/USD") formats.

    >>> is_usd_or_stablecoin_quoted("BTC/USD")
    True
    >>> is_usd_or_stablecoin_quoted("ETH-USDT")
    True
    >>> is_usd_or_stablecoin_quoted("BTC/EUR")
    False
    """
    upper = symbol.strip().upper()
    for sep in ("/", "-"):
        if sep in upper:
            quote = upper.rsplit(sep, 1)[1]
            return quote in ("USD", "USDT", "USDC")
    return False
