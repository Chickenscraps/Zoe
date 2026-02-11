/**
 * Tests for @zoe/trader — scanner, briefing, session handling
 */
import { describe, it, expect } from "vitest";
import {
  scanOptionChain,
  rankWithResearch,
  type ScanCandidate,
} from "../../services/trader/src/scanner.js";
import {
  getBriefingType,
  generateBriefing,
  shouldSendBriefing,
} from "../../services/trader/src/briefing.js";
import type { OptionContract, FeatureDaily, DailyPlan } from "../../services/shared/src/types.js";

// ─── Helpers ────────────────────────────────────────────────────────

function makeContract(overrides: Partial<OptionContract> = {}): OptionContract {
  return {
    ticker: "O:SPY260220C00500000",
    underlying: "SPY",
    expiry: new Date(Date.now() + 14 * 86400000).toISOString().split("T")[0]!,
    strike: 500,
    contract_type: "call",
    bid: 5.0,
    ask: 5.20,
    mid: 5.10,
    last: 5.10,
    volume: 500,
    open_interest: 2000,
    implied_volatility: 0.25,
    greeks: { delta: 0.35, gamma: 0.02, theta: -0.05, vega: 0.15 },
    ...overrides,
  };
}

function makePlan(): DailyPlan {
  return {
    date: "2026-02-10",
    watchlist: ["SPY", "QQQ"],
    proposed_plays: [
      {
        symbol: "SPY",
        strategy: "vertical_spread",
        direction: "long",
        entry_conditions: "IV > 0.20, delta 0.30-0.40",
        risk: 50,
        catalyst: "Earnings week",
      },
    ],
    market_context: "Bullish bias, low VIX",
    invalidation_levels: { SPY: 490 },
  };
}

// ─── Scanner Tests ──────────────────────────────────────────────────

describe("Scanner", () => {
  it("should filter contracts by volume", () => {
    const contracts = [
      makeContract({ volume: 500 }),  // passes
      makeContract({ volume: 10 }),   // fails
    ];
    const results = scanOptionChain(contracts, { minVolume: 100 });
    expect(results.length).toBe(1);
  });

  it("should filter contracts by open interest", () => {
    const contracts = [
      makeContract({ open_interest: 2000 }),  // passes
      makeContract({ open_interest: 100 }),    // fails
    ];
    const results = scanOptionChain(contracts, { minOpenInterest: 500 });
    expect(results.length).toBe(1);
  });

  it("should filter by IV range", () => {
    const contracts = [
      makeContract({ implied_volatility: 0.25 }),  // passes
      makeContract({ implied_volatility: 0.90 }),   // too high
      makeContract({ implied_volatility: 0.05 }),   // too low
    ];
    const results = scanOptionChain(contracts, { minIV: 0.15, maxIV: 0.80 });
    expect(results.length).toBe(1);
  });

  it("should filter by delta range", () => {
    const contracts = [
      makeContract({ greeks: { delta: 0.35, gamma: 0.02, theta: -0.05, vega: 0.15 } }),  // passes
      makeContract({ greeks: { delta: 0.05, gamma: 0.01, theta: -0.01, vega: 0.05 } }),   // too low
      makeContract({ greeks: { delta: 0.90, gamma: 0.01, theta: -0.15, vega: 0.25 } }),   // too high
    ];
    const results = scanOptionChain(contracts, { minDelta: 0.15, maxDelta: 0.50 });
    expect(results.length).toBe(1);
  });

  it("should sort by score descending", () => {
    const contracts = [
      makeContract({ volume: 200, open_interest: 1000 }),
      makeContract({ volume: 5000, open_interest: 10000 }),
    ];
    const results = scanOptionChain(contracts);
    expect(results.length).toBe(2);
    expect(results[0]!.score).toBeGreaterThanOrEqual(results[1]!.score);
  });

  it("should filter expired contracts", () => {
    const contracts = [
      makeContract({ expiry: "2020-01-01" }), // expired
      makeContract(), // valid
    ];
    const results = scanOptionChain(contracts);
    expect(results.length).toBe(1);
  });

  it("rankWithResearch should boost scores with positive sentiment", () => {
    const candidates: ScanCandidate[] = [
      { contract: makeContract(), score: 5, reasons: [] },
    ];
    const features: FeatureDaily[] = [
      {
        id: "feat-1",
        symbol: "SPY",
        date: "2026-02-10",
        features: { sentiment: 0.8, momentum: 0.6 },
        source_ids: [],
        created_at: new Date().toISOString(),
      },
    ];
    const ranked = rankWithResearch(candidates, features);
    expect(ranked[0]!.score).toBeGreaterThan(5);
    expect(ranked[0]!.reasons).toContain("bullish sentiment");
  });
});

// ─── Briefing Tests ─────────────────────────────────────────────────

describe("Briefing", () => {
  it("getBriefingType should return correct type by minutes", () => {
    expect(getBriefingType(20)).toBeNull();
    expect(getBriefingType(15)).toBe("15min");
    expect(getBriefingType(10)).toBe("10min");
    expect(getBriefingType(5)).toBe("5min");
    expect(getBriefingType(3)).toBe("5min");
    expect(getBriefingType(0)).toBe("at_open");
    expect(getBriefingType(-1)).toBe("at_open");
  });

  it("generateBriefing should create a briefing from a plan", () => {
    const plan = makePlan();
    const briefing = generateBriefing(plan, 15);
    expect(briefing).not.toBeNull();
    expect(briefing!.type).toBe("15min");
    expect(briefing!.watchlist).toEqual(["SPY", "QQQ"]);
    expect(briefing!.proposedPlays.length).toBe(1);
  });

  it("generateBriefing should return null when no type matches", () => {
    const plan = makePlan();
    const briefing = generateBriefing(plan, 30);
    expect(briefing).toBeNull();
  });

  it("generateBriefing should handle null plan gracefully", () => {
    const briefing = generateBriefing(null, 10);
    expect(briefing).not.toBeNull();
    expect(briefing!.watchlist).toEqual([]);
    expect(briefing!.proposedPlays).toEqual([]);
  });

  it("shouldSendBriefing should not repeat same type", () => {
    // Pre-market at 9:20 ET = 10 min to open
    const preMarket = new Date("2026-02-10T09:20:00-05:00");
    const type = shouldSendBriefing(null, preMarket);
    expect(type).toBe("10min");

    const type2 = shouldSendBriefing("10min", preMarket);
    expect(type2).toBeNull();
  });

  it("shouldSendBriefing should return null outside pre_market", () => {
    const marketHours = new Date("2026-02-10T12:00:00-05:00");
    expect(shouldSendBriefing(null, marketHours)).toBeNull();
  });
});
