"""Tests for Bollinger Bands calculation in PriceCache."""
import pytest
import time
from services.crypto_trader.price_cache import PriceCache


def _populate_cache(cache: PriceCache, symbol: str, prices: list[float]):
    """Populate a PriceCache with synthetic price ticks."""
    base_ts = time.time()
    for i, price in enumerate(prices):
        cache.record(symbol, bid=price * 0.999, ask=price * 1.001, ts=base_ts + i)


class TestBollingerBands:
    """Test the bollinger_bands method on PriceCache."""

    def _make_cache(self, prices, symbol="ETH-USD"):
        cache = PriceCache(capacity_per_symbol=500)
        _populate_cache(cache, symbol, prices)
        return cache, symbol

    def test_insufficient_data_returns_none(self):
        """BB needs at least period=20 data points."""
        cache, sym = self._make_cache([100.0] * 10)
        result = cache.bollinger_bands(sym)
        assert result is None

    def test_flat_prices_zero_bandwidth(self):
        """Flat prices produce zero bandwidth."""
        cache, sym = self._make_cache([100.0] * 50)
        result = cache.bollinger_bands(sym)
        assert result is not None
        assert abs(result["bandwidth"]) < 0.01
        # Upper, middle, lower should be very close to the flat price
        assert abs(result["middle"] - 100.0) < 0.5  # slight bid/ask spread

    def test_volatile_prices_wide_bands(self):
        """Oscillating prices produce wide bands."""
        prices = [90.0 if i % 2 == 0 else 110.0 for i in range(60)]
        cache, sym = self._make_cache(prices)
        result = cache.bollinger_bands(sym)
        assert result is not None
        assert result["bandwidth"] > 0
        assert result["upper"] > result["middle"]
        assert result["lower"] < result["middle"]

    def test_percent_b_at_lower_band(self):
        """Price near lower band has %B near 0."""
        prices = [100.0] * 40 + [80.0] * 10
        cache, sym = self._make_cache(prices)
        result = cache.bollinger_bands(sym)
        assert result is not None
        assert result["percent_b"] < 0.3

    def test_percent_b_at_upper_band(self):
        """Price near upper band has %B near 1."""
        prices = [100.0] * 40 + [120.0] * 10
        cache, sym = self._make_cache(prices)
        result = cache.bollinger_bands(sym)
        assert result is not None
        assert result["percent_b"] > 0.7

    def test_squeeze_detection(self):
        """Squeeze is detected when bandwidth is in lowest 20th percentile."""
        wide = [80.0 if i % 2 == 0 else 120.0 for i in range(40)]
        narrow = [100.0] * 30
        prices = wide + narrow
        cache, sym = self._make_cache(prices)
        result = cache.bollinger_bands(sym)
        assert result is not None
        assert result["squeeze"] is True

    def test_no_squeeze_volatile(self):
        """No squeeze during volatile periods."""
        prices = [80.0 if i % 2 == 0 else 120.0 for i in range(60)]
        cache, sym = self._make_cache(prices)
        result = cache.bollinger_bands(sym)
        assert result is not None
        assert result["squeeze"] is False

    def test_result_keys(self):
        """Result has all expected keys."""
        cache, sym = self._make_cache([100.0] * 50)
        result = cache.bollinger_bands(sym)
        assert result is not None
        expected = {"upper", "middle", "lower", "bandwidth", "percent_b", "squeeze"}
        assert set(result.keys()) == expected

    def test_upper_always_above_lower(self):
        """Upper band is always >= lower band."""
        import random
        random.seed(42)
        prices = [100 + random.gauss(0, 5) for _ in range(100)]
        cache, sym = self._make_cache(prices)
        result = cache.bollinger_bands(sym)
        assert result is not None
        assert result["upper"] >= result["lower"]

    def test_unknown_symbol_returns_none(self):
        """Unknown symbol returns None."""
        cache = PriceCache()
        assert cache.bollinger_bands("FAKE-USD") is None
