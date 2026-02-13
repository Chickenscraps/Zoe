"""Tests for RepositionPolicy decisions and price computation."""
from __future__ import annotations

import pytest

from .reposition_policy import RepositionPolicy, RepositionDecision


@pytest.fixture
def policy():
    return RepositionPolicy(
        ttl_entry=60,
        ttl_exit=30,
        max_reprice_attempts=3,
        reprice_step_bps=5.0,
        max_cross_spread_bps=20.0,
        liquidity_guard_spread_pct=0.5,
    )


class TestTTL:
    def test_entry_ttl(self, policy):
        assert policy.ttl_for("buy", "entry") == 60

    def test_exit_ttl(self, policy):
        assert policy.ttl_for("sell", "exit") == 30

    def test_sell_uses_exit_ttl(self, policy):
        assert policy.ttl_for("sell", "entry") == 30


class TestShouldReposition:
    def test_reposition_when_under_max(self, policy):
        result = policy.should_reposition(
            side="buy", replace_count=1, current_limit=100.0,
            bid=99.0, ask=101.0, spread_pct=0.2,
        )
        assert result == RepositionDecision.REPOSITION

    def test_cancel_at_max_reprices(self, policy):
        result = policy.should_reposition(
            side="buy", replace_count=3, current_limit=100.0,
            bid=99.0, ask=101.0, spread_pct=0.2,
        )
        assert result == RepositionDecision.CANCEL

    def test_cancel_liquidity_on_wide_spread(self, policy):
        result = policy.should_reposition(
            side="buy", replace_count=0, current_limit=100.0,
            bid=99.0, ask=101.0, spread_pct=0.6,
        )
        assert result == RepositionDecision.CANCEL_LIQUIDITY

    def test_hold_when_market_order(self, policy):
        result = policy.should_reposition(
            side="buy", replace_count=0, current_limit=None,
            bid=99.0, ask=101.0, spread_pct=0.2,
        )
        assert result == RepositionDecision.HOLD


class TestComputeNewPrice:
    def test_buy_steps_up(self, policy):
        new = policy.compute_new_price(
            side="buy", current_limit=99.0,
            bid=99.0, ask=101.0, replace_count=0,
        )
        # Should step up from 99.0 toward ask
        assert new > 99.0

    def test_sell_steps_down(self, policy):
        new = policy.compute_new_price(
            side="sell", current_limit=101.0,
            bid=99.0, ask=101.0, replace_count=0,
        )
        # Should step down from 101.0 toward bid
        assert new < 101.0

    def test_buy_capped_at_max_cross(self, policy):
        # With many replace_counts, shouldn't exceed max_cross from bid
        mid = 100.0
        max_cross = mid * (20.0 / 10_000)
        new = policy.compute_new_price(
            side="buy", current_limit=99.0,
            bid=99.0, ask=101.0, replace_count=100,
        )
        assert new <= 99.0 + max_cross + 0.01  # small float tolerance

    def test_sell_floored_at_max_cross(self, policy):
        mid = 100.0
        max_cross = mid * (20.0 / 10_000)
        new = policy.compute_new_price(
            side="sell", current_limit=101.0,
            bid=99.0, ask=101.0, replace_count=100,
        )
        assert new >= 101.0 - max_cross - 0.01

    def test_step_increases_with_replace_count(self, policy):
        p0 = policy.compute_new_price(side="buy", current_limit=99.0, bid=99.0, ask=101.0, replace_count=0)
        p1 = policy.compute_new_price(side="buy", current_limit=99.0, bid=99.0, ask=101.0, replace_count=1)
        assert p1 > p0
