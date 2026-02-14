"""Tests for Kraken symbol normalization."""
import pytest
from integrations.kraken_client.symbols import (
    to_kraken,
    from_kraken,
    populate_from_asset_pairs,
    _normalize_asset,
    _convert_wsname_to_v2,
    get_ws_symbol,
    get_all_internal_symbols,
)


# Minimal AssetPairs-style fixture for cache population
MOCK_PAIRS = {
    "XXBTZUSD": {
        "base": "XXBT",
        "quote": "ZUSD",
        "wsname": "XBT/USD",
        "altname": "XBTUSD",
    },
    "XETHZUSD": {
        "base": "XETH",
        "quote": "ZUSD",
        "wsname": "ETH/USD",
        "altname": "ETHUSD",
    },
    "SOLUSD": {
        "base": "SOL",
        "quote": "USD",
        "wsname": "SOL/USD",
        "altname": "SOLUSD",
    },
    "XDGUSD": {
        "base": "XXDG",
        "quote": "ZUSD",
        "wsname": "XDG/USD",
        "altname": "DOGEUSD",
    },
    "XXRPZUSD": {
        "base": "XXRP",
        "quote": "ZUSD",
        "wsname": "XRP/USD",
        "altname": "XRPUSD",
    },
}


@pytest.fixture(autouse=True)
def _populate_cache():
    """Populate symbol cache before each test, clear after."""
    from integrations.kraken_client import symbols

    # Save and clear
    old_pair = dict(symbols._pair_cache)
    old_rev = dict(symbols._reverse_cache)
    old_ws = dict(symbols._ws_pair_cache)
    old_ws_rev = dict(symbols._ws_reverse_cache)

    symbols._pair_cache.clear()
    symbols._reverse_cache.clear()
    symbols._ws_pair_cache.clear()
    symbols._ws_reverse_cache.clear()

    populate_from_asset_pairs(MOCK_PAIRS)

    yield

    # Restore
    symbols._pair_cache.clear()
    symbols._reverse_cache.clear()
    symbols._ws_pair_cache.clear()
    symbols._ws_reverse_cache.clear()
    symbols._pair_cache.update(old_pair)
    symbols._reverse_cache.update(old_rev)
    symbols._ws_pair_cache.update(old_ws)
    symbols._ws_reverse_cache.update(old_ws_rev)


class TestNormalizeAsset:
    """Test raw Kraken asset name normalization."""

    def test_xxbt_to_btc(self):
        assert _normalize_asset("XXBT") == "BTC"

    def test_xeth_to_eth(self):
        assert _normalize_asset("XETH") == "ETH"

    def test_zusd_to_usd(self):
        assert _normalize_asset("ZUSD") == "USD"

    def test_sol_unchanged(self):
        assert _normalize_asset("SOL") == "SOL"

    def test_xxdg_to_doge(self):
        assert _normalize_asset("XXDG") == "DOGE"

    def test_xbt_to_btc(self):
        """Three-letter legacy name."""
        assert _normalize_asset("XBT") == "BTC"


class TestConvertWsnameV2:
    """Test WS v1 -> v2 name conversion."""

    def test_xbt_becomes_btc(self):
        assert _convert_wsname_to_v2("XBT/USD") == "BTC/USD"

    def test_xdg_becomes_doge(self):
        assert _convert_wsname_to_v2("XDG/USD") == "DOGE/USD"

    def test_eth_unchanged(self):
        assert _convert_wsname_to_v2("ETH/USD") == "ETH/USD"

    def test_no_slash_passthrough(self):
        assert _convert_wsname_to_v2("XBTUSD") == "XBTUSD"


class TestToKraken:
    """Test internal -> Kraken conversion."""

    def test_btc_rest(self):
        result = to_kraken("BTC-USD", for_ws=False)
        assert result == "XXBTZUSD"

    def test_btc_ws(self):
        result = to_kraken("BTC-USD", for_ws=True)
        assert result == "BTC/USD"

    def test_eth_rest(self):
        result = to_kraken("ETH-USD", for_ws=False)
        assert result == "XETHZUSD"

    def test_eth_ws(self):
        result = to_kraken("ETH-USD", for_ws=True)
        assert result == "ETH/USD"

    def test_sol_ws(self):
        result = to_kraken("SOL-USD", for_ws=True)
        assert result == "SOL/USD"

    def test_doge_ws(self):
        """DOGE should use standard name in WS v2, not XDG."""
        result = to_kraken("DOGE-USD", for_ws=True)
        assert result == "DOGE/USD"

    def test_get_ws_symbol_convenience(self):
        assert get_ws_symbol("BTC-USD") == "BTC/USD"

    def test_unknown_ws_fallback(self):
        """Unknown symbols get simple slash-format for WS."""
        result = to_kraken("FOO-BAR", for_ws=True)
        assert result == "FOO/BAR"

    def test_unknown_rest_fallback(self):
        result = to_kraken("FOO-BAR", for_ws=False)
        assert result == "FOOBAR"


class TestFromKraken:
    """Test Kraken -> internal conversion."""

    def test_rest_format(self):
        assert from_kraken("XXBTZUSD") == "BTC-USD"

    def test_ws_v2_format(self):
        assert from_kraken("BTC/USD") == "BTC-USD"

    def test_ws_v1_format(self):
        """v1 format (XBT/USD) should also resolve."""
        assert from_kraken("XBT/USD") == "BTC-USD"

    def test_eth_rest(self):
        assert from_kraken("XETHZUSD") == "ETH-USD"

    def test_altname(self):
        """Altname like XBTUSD should resolve."""
        assert from_kraken("XBTUSD") == "BTC-USD"

    def test_unknown_ws(self):
        assert from_kraken("UNKNOWN/USD") == "UNKNOWN-USD"


class TestRoundTrip:
    """Test round-trip conversions."""

    @pytest.mark.parametrize("symbol", ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "XRP-USD"])
    def test_rest_round_trip(self, symbol):
        """internal -> REST -> internal."""
        kraken = to_kraken(symbol, for_ws=False)
        back = from_kraken(kraken)
        assert back == symbol, f"REST round-trip failed: {symbol} -> {kraken} -> {back}"

    @pytest.mark.parametrize("symbol", ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "XRP-USD"])
    def test_ws_round_trip(self, symbol):
        """internal -> WS -> internal."""
        kraken = to_kraken(symbol, for_ws=True)
        back = from_kraken(kraken)
        assert back == symbol, f"WS round-trip failed: {symbol} -> {kraken} -> {back}"


class TestCachePopulation:
    """Test cache population from AssetPairs."""

    def test_pair_count(self):
        from integrations.kraken_client import symbols
        symbols._pair_cache.clear()
        symbols._reverse_cache.clear()
        symbols._ws_pair_cache.clear()
        symbols._ws_reverse_cache.clear()
        count = populate_from_asset_pairs(MOCK_PAIRS)
        assert count == 5

    def test_get_all_symbols(self):
        syms = get_all_internal_symbols()
        assert "BTC-USD" in syms
        assert "ETH-USD" in syms
        assert len(syms) == 5
