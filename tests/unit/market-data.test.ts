/**
 * Tests for @zoe/market-data — cache, normalization, service error handling
 * NO real API calls — all mocked.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { TTLCache } from "../../services/market-data/src/cache.js";
import {
  normalizeQuote,
  normalizeOHLCV,
  normalizeOptionContract,
  normalizeGreeks,
  type PolygonLastTrade,
  type PolygonLastQuote,
  type PolygonAgg,
  type PolygonOptionSnapshot,
} from "../../services/market-data/src/normalize.js";

// ─── TTLCache Tests ─────────────────────────────────────────────────

describe("TTLCache", () => {
  let cache: TTLCache<string>;

  beforeEach(() => {
    cache = new TTLCache<string>(1, 0); // 1 second TTL, no auto-cleanup
  });

  afterEach(() => {
    cache.destroy();
  });

  it("should store and retrieve values", () => {
    cache.set("key1", "value1");
    expect(cache.get("key1")).toBe("value1");
  });

  it("should return null for missing keys", () => {
    expect(cache.get("nonexistent")).toBeNull();
  });

  it("should return null for expired entries", async () => {
    cache.set("key1", "value1");
    expect(cache.get("key1")).toBe("value1");

    // Wait for TTL to expire
    await new Promise((r) => setTimeout(r, 1100));
    expect(cache.get("key1")).toBeNull();
  });

  it("should support has() check", () => {
    cache.set("a", "b");
    expect(cache.has("a")).toBe(true);
    expect(cache.has("z")).toBe(false);
  });

  it("should invalidate specific keys", () => {
    cache.set("a", "1");
    cache.set("b", "2");
    cache.invalidate("a");
    expect(cache.get("a")).toBeNull();
    expect(cache.get("b")).toBe("2");
  });

  it("should clear all entries", () => {
    cache.set("a", "1");
    cache.set("b", "2");
    cache.clear();
    expect(cache.get("a")).toBeNull();
    expect(cache.get("b")).toBeNull();
  });

  it("should support custom TTL per entry", async () => {
    // Set entry with 2 second custom TTL
    cache.set("long", "lived", 2000);
    cache.set("short", "lived"); // uses default 1s

    await new Promise((r) => setTimeout(r, 1100));
    expect(cache.get("short")).toBeNull();
    expect(cache.get("long")).toBe("lived");
  });
});

// ─── Normalization Tests ────────────────────────────────────────────

describe("normalizeQuote", () => {
  it("should normalize a complete trade + quote", () => {
    const trade: PolygonLastTrade = { T: "AAPL", p: 150.25, s: 100, t: 1700000000000000000 };
    const quote: PolygonLastQuote = { T: "AAPL", p: 150.20, P: 150.30, s: 50, S: 50 };

    const result = normalizeQuote("AAPL", trade, quote);
    expect(result.symbol).toBe("AAPL");
    expect(result.price).toBe(150.25);
    expect(result.bid).toBe(150.20);
    expect(result.ask).toBe(150.30);
    expect(result.timestamp).toBe(1700000000000);
  });

  it("should handle null trade gracefully", () => {
    const quote: PolygonLastQuote = { p: 100.0, P: 100.10 };
    const result = normalizeQuote("SPY", null, quote);
    expect(result.price).toBe(0);
    expect(result.bid).toBe(100.0);
    expect(result.ask).toBe(100.10);
  });

  it("should handle null quote gracefully", () => {
    const trade: PolygonLastTrade = { p: 200.0 };
    const result = normalizeQuote("QQQ", trade, null);
    expect(result.price).toBe(200.0);
    expect(result.bid).toBe(0);
    expect(result.ask).toBe(0);
  });
});

describe("normalizeOHLCV", () => {
  it("should normalize an aggregate bar", () => {
    const agg: PolygonAgg = { o: 100, h: 105, l: 99, c: 103, v: 1000000, t: 1700000000000 };
    const result = normalizeOHLCV(agg);
    expect(result.open).toBe(100);
    expect(result.high).toBe(105);
    expect(result.low).toBe(99);
    expect(result.close).toBe(103);
    expect(result.volume).toBe(1000000);
    expect(result.timestamp).toBe(1700000000000);
  });

  it("should default missing fields to 0", () => {
    const result = normalizeOHLCV({});
    expect(result.open).toBe(0);
    expect(result.close).toBe(0);
    expect(result.volume).toBe(0);
  });
});

describe("normalizeGreeks", () => {
  it("should normalize full greeks", () => {
    const result = normalizeGreeks({ delta: 0.45, gamma: 0.03, theta: -0.05, vega: 0.12 });
    expect(result.delta).toBe(0.45);
    expect(result.gamma).toBe(0.03);
    expect(result.theta).toBe(-0.05);
    expect(result.vega).toBe(0.12);
  });

  it("should return nulls for missing greeks", () => {
    const result = normalizeGreeks(undefined);
    expect(result.delta).toBeNull();
    expect(result.gamma).toBeNull();
  });
});

describe("normalizeOptionContract", () => {
  it("should normalize a full option snapshot", () => {
    const snap: PolygonOptionSnapshot = {
      details: {
        ticker: "O:SPY260220C00500000",
        expiration_date: "2026-02-20",
        strike_price: 500,
        contract_type: "call",
      },
      greeks: { delta: 0.5, gamma: 0.02, theta: -0.1, vega: 0.2 },
      implied_volatility: 0.25,
      day: { close: 5.50, volume: 1500, open_interest: 3000 },
      last_quote: { bid: 5.40, ask: 5.60 },
      underlying_asset: { ticker: "SPY" },
    };

    const result = normalizeOptionContract(snap);
    expect(result.ticker).toBe("O:SPY260220C00500000");
    expect(result.underlying).toBe("SPY");
    expect(result.strike).toBe(500);
    expect(result.contract_type).toBe("call");
    expect(result.bid).toBe(5.40);
    expect(result.ask).toBe(5.60);
    expect(result.mid).toBe(5.50);
    expect(result.implied_volatility).toBe(0.25);
    expect(result.greeks.delta).toBe(0.5);
  });

  it("should handle missing optional fields", () => {
    const result = normalizeOptionContract({});
    expect(result.ticker).toBe("");
    expect(result.underlying).toBe("");
    expect(result.strike).toBe(0);
    expect(result.bid).toBe(0);
    expect(result.ask).toBe(0);
    expect(result.mid).toBe(0);
  });
});
