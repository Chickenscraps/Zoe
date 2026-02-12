"""Tests for MACD calculation in PriceCache."""
import pytest
import time
from services.crypto_trader.price_cache import PriceCache, PriceTick


def _populate_cache(cache: PriceCache, symbol: str, prices: list[float]):
    """Populate a PriceCache with synthetic price ticks."""
    base_ts = time.time()
    for i, price in enumerate(prices):
        cache.record(symbol, bid=price * 0.999, ask=price * 1.001, ts=base_ts + i)


class TestComputeEmaSeries:
    """Test the _compute_ema_series static helper."""

    def test_returns_same_length_when_enough_data(self):
        """Series >= span returns same-length result."""
        result = PriceCache._compute_ema_series([50.0] * 30, 12)
        assert len(result) == 30

    def test_returns_empty_when_too_short(self):
        """Series shorter than span returns empty."""
        result = PriceCache._compute_ema_series([100.0] * 5, 12)
        assert result == []

    def test_constant_series(self):
        """Constant input should produce constant EMA."""
        values = [50.0] * 30
        result = PriceCache._compute_ema_series(values, 12)
        assert len(result) == 30
        for v in result:
            assert abs(v - 50.0) < 1e-10

    def test_uptrend_lags(self):
        """EMA on uptrend should lag behind actual values."""
        values = list(range(1, 31))
        result = PriceCache._compute_ema_series(values, 12)
        assert result[-1] < values[-1]
        assert result[-1] > values[-1] / 2

    def test_empty_series(self):
        """Empty input returns empty output."""
        result = PriceCache._compute_ema_series([], 12)
        assert result == []


class TestMACDCalculation:
    """Test the MACD method on PriceCache."""

    def _make_cache(self, prices: list[float], symbol: str = "BTC-USD") -> tuple[PriceCache, str]:
        """Create cache with prices via update method."""
        cache = PriceCache(capacity_per_symbol=500)
        _populate_cache(cache, symbol, prices)
        return cache, symbol

    def test_insufficient_data_returns_none(self):
        """MACD needs enough data for slow+signal periods."""
        cache, sym = self._make_cache([100.0] * 10)
        result = cache.macd(sym)
        assert result is None

    def test_flat_prices_near_zero_histogram(self):
        """Flat prices produce near-zero MACD histogram."""
        cache, sym = self._make_cache([100.0] * 100)
        result = cache.macd(sym)
        assert result is not None
        assert abs(result["histogram"]) < 0.01

    def test_uptrend_positive_histogram(self):
        """Sustained uptrend produces positive MACD histogram."""
        prices = [100.0] * 50 + [100.0 + i * 2 for i in range(50)]
        cache, sym = self._make_cache(prices)
        result = cache.macd(sym)
        assert result is not None
        assert result["histogram"] > 0
        assert result["macd_line"] > 0

    def test_downtrend_negative_histogram(self):
        """Sustained downtrend produces negative MACD histogram."""
        prices = [200.0] * 50 + [200.0 - i * 2 for i in range(50)]
        cache, sym = self._make_cache(prices)
        result = cache.macd(sym)
        assert result is not None
        assert result["histogram"] < 0
        assert result["macd_line"] < 0

    def test_crossover_detection(self):
        """Crossover flag is an int in {-1, 0, 1}."""
        prices = [100.0] * 60 + [100.0 + i * 5 for i in range(40)]
        cache, sym = self._make_cache(prices)
        result = cache.macd(sym)
        assert result is not None
        assert result["crossover"] in (-1, 0, 1)

    def test_histogram_slope_key(self):
        """Histogram slope is present in result."""
        prices = [100.0] * 50 + [100.0 + i for i in range(50)]
        cache, sym = self._make_cache(prices)
        result = cache.macd(sym)
        assert result is not None
        assert "histogram_slope" in result

    def test_crypto_optimized_params(self):
        """macd_crypto uses 8/17/9 parameters."""
        prices = [100.0] * 50 + [100.0 + i for i in range(50)]
        cache, sym = self._make_cache(prices)
        result = cache.macd_crypto(sym)
        assert result is not None
        assert result["histogram"] > 0

    def test_unknown_symbol_returns_none(self):
        """Unknown symbol returns None."""
        cache = PriceCache()
        assert cache.macd("FAKE-USD") is None

    def test_result_keys(self):
        """Result dict has all expected keys."""
        prices = [100.0] * 100
        cache, sym = self._make_cache(prices)
        result = cache.macd(sym)
        assert result is not None
        expected_keys = {"macd_line", "signal_line", "histogram", "histogram_slope", "crossover"}
        assert set(result.keys()) == expected_keys
