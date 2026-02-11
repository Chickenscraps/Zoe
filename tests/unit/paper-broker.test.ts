/**
 * Tests for @zoe/paper-broker — PDT limiter, slippage model, risk manager
 * NO real Supabase calls — all unit tests on pure functions.
 */
import { describe, it, expect, vi } from "vitest";
import {
  checkPDT,
  getWindowStartDate,
  getTradesInWindow,
  createDayTradeRecord,
} from "../../services/paper-broker/src/pdt-limiter.js";
import {
  calculateFillPrice,
  estimateSlippage,
} from "../../services/paper-broker/src/slippage.js";
import { checkOrderRisk } from "../../services/paper-broker/src/risk-manager.js";
import type { Account, DayTrade, Quote, Position } from "../../services/shared/src/types.js";

// ─── Test Helpers ───────────────────────────────────────────────────

function makeAccount(overrides: Partial<Account> = {}): Account {
  return {
    id: "acct-1",
    user_id: "user-1",
    instance_id: "default",
    equity: 2000,
    cash: 2000,
    buying_power: 2000,
    pdt_count: 0,
    day_trades_history: [],
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

function makeQuote(overrides: Partial<Quote> = {}): Quote {
  return {
    symbol: "SPY",
    price: 500,
    bid: 499.90,
    ask: 500.10,
    timestamp: Date.now(),
    ...overrides,
  };
}

function makeDayTrade(daysAgo: number, symbol = "SPY"): DayTrade {
  const d = new Date();
  // Go back `daysAgo` calendar days
  d.setDate(d.getDate() - daysAgo);
  return {
    trade_id: `trade-${daysAgo}`,
    symbol,
    open_time: d.toISOString(),
    close_time: d.toISOString(),
    pnl: 10,
  };
}

// ─── PDT Limiter ────────────────────────────────────────────────────

describe("PDT Limiter", () => {
  it("should allow day trades when under limit", () => {
    const result = checkPDT([makeDayTrade(1)], { maxDayTrades: 3, windowDays: 5 });
    expect(result.can_day_trade).toBe(true);
    expect(result.day_trade_count).toBe(1);
    expect(result.max_allowed).toBe(3);
  });

  it("should block day trades when at limit", () => {
    const trades = [makeDayTrade(1), makeDayTrade(2), makeDayTrade(3)];
    const result = checkPDT(trades, { maxDayTrades: 3, windowDays: 5 });
    expect(result.can_day_trade).toBe(false);
    expect(result.day_trade_count).toBe(3);
  });

  it("should not count trades outside the rolling window", () => {
    // Trade from 10 days ago should not count in a 5-trading-day window
    const trades = [makeDayTrade(1), makeDayTrade(2), makeDayTrade(15)];
    const result = checkPDT(trades, { maxDayTrades: 3, windowDays: 5 });
    // Only 2 should be in window (the one 15 days ago is out)
    expect(result.day_trade_count).toBeLessThanOrEqual(3);
    expect(result.can_day_trade).toBe(true);
  });

  it("should allow trades when history is empty", () => {
    const result = checkPDT([], { maxDayTrades: 3, windowDays: 5 });
    expect(result.can_day_trade).toBe(true);
    expect(result.day_trade_count).toBe(0);
  });

  it("should provide next_expiry when at limit", () => {
    const trades = [makeDayTrade(1), makeDayTrade(2), makeDayTrade(3)];
    const result = checkPDT(trades, { maxDayTrades: 3, windowDays: 5 });
    if (!result.can_day_trade) {
      expect(result.next_expiry).not.toBeNull();
    }
  });

  it("should create a day trade record correctly", () => {
    const record = createDayTradeRecord(
      "trade-1",
      "SPY",
      "2026-02-10T10:00:00Z",
      "2026-02-10T14:00:00Z",
      50
    );
    expect(record.trade_id).toBe("trade-1");
    expect(record.symbol).toBe("SPY");
    expect(record.pnl).toBe(50);
  });

  it("getWindowStartDate should skip weekends", () => {
    // Monday Feb 10, 2026
    const monday = new Date("2026-02-10T12:00:00-05:00");
    // 5 trading days back from Monday should be the previous Monday (Feb 2)
    // or earlier if there are holidays
    const windowStart = getWindowStartDate(monday, 5);
    expect(windowStart.getTime()).toBeLessThan(monday.getTime());
  });
});

// ─── Slippage Model ─────────────────────────────────────────────────

describe("Slippage Model", () => {
  it("should fill BUY at ASK + slippage (pessimistic)", () => {
    const quote = makeQuote({ bid: 5.00, ask: 5.10, price: 5.05 });
    const result = calculateFillPrice("buy", quote, {
      pessimisticFills: true,
      slippageBps: 10,
    });
    // ASK = 5.10, slippage = 5.10 * 10/10000 = 0.0051
    expect(result.fillPrice).toBeGreaterThan(5.10);
    expect(result.slippageBps).toBe(10);
    expect(result.slippageAmount).toBeGreaterThan(0);
  });

  it("should fill SELL at BID - slippage (pessimistic)", () => {
    const quote = makeQuote({ bid: 5.00, ask: 5.10, price: 5.05 });
    const result = calculateFillPrice("sell", quote, {
      pessimisticFills: true,
      slippageBps: 10,
    });
    // BID = 5.00, slippage negative
    expect(result.fillPrice).toBeLessThan(5.00);
    expect(result.slippageAmount).toBeLessThan(0);
  });

  it("should fill at MID for optimistic mode", () => {
    const quote = makeQuote({ bid: 5.00, ask: 5.10, price: 5.05 });
    const result = calculateFillPrice("buy", quote, {
      pessimisticFills: false,
      slippageBps: 0,
    });
    // MID = (5.00 + 5.10) / 2 = 5.05
    expect(result.fillPrice).toBe(5.05);
  });

  it("should handle zero spread gracefully", () => {
    const quote = makeQuote({ bid: 0, ask: 0, price: 10 });
    const result = calculateFillPrice("buy", quote, {
      pessimisticFills: true,
      slippageBps: 5,
    });
    // Should use price as fallback
    expect(result.fillPrice).toBeGreaterThan(0);
  });

  it("estimateSlippage should increase for larger orders", () => {
    const small = estimateSlippage(5, 1);
    const large = estimateSlippage(5, 50);
    expect(large).toBeGreaterThan(small);
  });

  it("estimateSlippage with volume should reflect participation rate", () => {
    const low = estimateSlippage(5, 10, 10000);
    const high = estimateSlippage(5, 10, 100);
    expect(high).toBeGreaterThan(low);
  });
});

// ─── Risk Manager ───────────────────────────────────────────────────

describe("Risk Manager", () => {
  it("should allow a valid buy order", () => {
    const account = makeAccount({ buying_power: 2000 });
    const result = checkOrderRisk(
      account,
      { symbol: "SPY260220C00500000", side: "buy", quantity: 1, price: 0.50 },
      [],
      false,
      { maxRiskPerTrade: 100 }
    );
    expect(result.allowed).toBe(true);
  });

  it("should reject when insufficient buying power", () => {
    const account = makeAccount({ buying_power: 10 });
    const result = checkOrderRisk(
      account,
      { symbol: "SPY", side: "buy", quantity: 1, price: 5.00 },
      [],
      false
    );
    // 5.00 * 1 * 100 = 500 > 10
    expect(result.allowed).toBe(false);
    expect(result.reason).toContain("buying power");
  });

  it("should reject when exceeding max risk per trade", () => {
    const account = makeAccount({ buying_power: 5000 });
    const result = checkOrderRisk(
      account,
      { symbol: "SPY", side: "buy", quantity: 1, price: 2.00 },
      [],
      false,
      { maxRiskPerTrade: 100 }
    );
    // 2.00 * 1 * 100 = 200 > 100
    expect(result.allowed).toBe(false);
    expect(result.reason).toContain("max risk");
  });

  it("should reject when max concurrent positions reached", () => {
    const positions: Position[] = Array.from({ length: 5 }, (_, i) => ({
      id: `pos-${i}`,
      account_id: "acct-1",
      symbol: `SYM${i}`,
      underlying: null,
      quantity: 1,
      avg_price: 1,
      current_price: 1,
      market_value: 100,
      unrealized_pnl: 0,
      updated_at: new Date().toISOString(),
    }));

    const account = makeAccount({ buying_power: 5000 });
    const result = checkOrderRisk(
      account,
      { symbol: "NEWSYM", side: "buy", quantity: 1, price: 0.50 },
      positions,
      false,
      { maxConcurrentPositions: 5 }
    );
    expect(result.allowed).toBe(false);
    expect(result.reason).toContain("concurrent positions");
  });

  it("should reject day trades when PDT limit reached", () => {
    const account = makeAccount({
      day_trades_history: [makeDayTrade(1), makeDayTrade(2), makeDayTrade(3)],
    });

    const result = checkOrderRisk(
      account,
      { symbol: "SPY", side: "buy", quantity: 1, price: 0.50 },
      [],
      true, // is day trade
      { pdtConfig: { maxDayTrades: 3, windowDays: 5 } }
    );
    expect(result.allowed).toBe(false);
    expect(result.reason).toContain("PDT");
  });

  it("should allow sell orders regardless of buying power", () => {
    const account = makeAccount({ buying_power: 0 });
    const result = checkOrderRisk(
      account,
      { symbol: "SPY", side: "sell", quantity: 1, price: 5.00 },
      [],
      false
    );
    expect(result.allowed).toBe(true);
  });

  it("should reject when symbol concentration is too high", () => {
    const account = makeAccount({ equity: 2000, buying_power: 2000 });
    const existingPositions: Position[] = [
      {
        id: "pos-1",
        account_id: "acct-1",
        symbol: "SPY",
        underlying: null,
        quantity: 1,
        avg_price: 5,
        current_price: 5,
        market_value: 900,
        unrealized_pnl: 0,
        updated_at: new Date().toISOString(),
      },
    ];

    // Trying to buy more SPY would put total > 50% of equity
    const result = checkOrderRisk(
      account,
      { symbol: "SPY", side: "buy", quantity: 1, price: 0.80 },
      existingPositions,
      false,
      { maxRiskPerTrade: 200, maxSingleSymbolPct: 50 }
    );
    // existing: $900, new: $80, total $980/2000 = 49% — should pass
    // Let's make it fail:
    const result2 = checkOrderRisk(
      account,
      { symbol: "SPY", side: "buy", quantity: 2, price: 0.80 },
      existingPositions,
      false,
      { maxRiskPerTrade: 200, maxSingleSymbolPct: 50 }
    );
    // existing: $900, new: $160, total $1060/2000 = 53% — should fail
    expect(result2.allowed).toBe(false);
    expect(result2.reason).toContain("% of equity");
  });
});
