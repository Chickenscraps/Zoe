/**
 * Tests for @zoe/strategy-lab — gate evaluation and experiment metrics
 */
import { describe, it, expect } from "vitest";
import { evaluateGates } from "../../services/strategy-lab/src/gates.js";
import type { ExperimentMetrics, GateCriteria } from "../../services/shared/src/types.js";

// ─── Helpers ────────────────────────────────────────────────────────

function makeMetrics(overrides: Partial<ExperimentMetrics> = {}): ExperimentMetrics {
  return {
    total_trades: 50,
    win_rate: 0.55,
    profit_factor: 1.8,
    max_drawdown: 0.12,
    sharpe_ratio: 1.2,
    total_pnl: 500,
    avg_pnl_per_trade: 10,
    ...overrides,
  };
}

function makeCriteria(overrides: Partial<GateCriteria> = {}): GateCriteria {
  return {
    min_trades: 30,
    min_win_rate: 0.50,
    max_drawdown: 0.20,
    min_profit_factor: 1.5,
    min_sharpe: null,
    ...overrides,
  };
}

// ─── Gate Evaluation Tests ──────────────────────────────────────────

describe("Gate Evaluation", () => {
  it("should pass when all criteria are met", () => {
    const result = evaluateGates(makeMetrics(), makeCriteria());
    expect(result.passed).toBe(true);
    expect(result.details.every((d) => d.passed)).toBe(true);
  });

  it("should fail when total_trades is below minimum", () => {
    const result = evaluateGates(
      makeMetrics({ total_trades: 10 }),
      makeCriteria({ min_trades: 30 })
    );
    expect(result.passed).toBe(false);
    const failed = result.details.find((d) => d.gate === "min_trades");
    expect(failed?.passed).toBe(false);
  });

  it("should fail when win_rate is below minimum", () => {
    const result = evaluateGates(
      makeMetrics({ win_rate: 0.35 }),
      makeCriteria({ min_win_rate: 0.50 })
    );
    expect(result.passed).toBe(false);
    const failed = result.details.find((d) => d.gate === "min_win_rate");
    expect(failed?.passed).toBe(false);
  });

  it("should fail when drawdown exceeds maximum", () => {
    const result = evaluateGates(
      makeMetrics({ max_drawdown: 0.35 }),
      makeCriteria({ max_drawdown: 0.20 })
    );
    expect(result.passed).toBe(false);
    const failed = result.details.find((d) => d.gate === "max_drawdown");
    expect(failed?.passed).toBe(false);
  });

  it("should fail when profit_factor is below minimum", () => {
    const result = evaluateGates(
      makeMetrics({ profit_factor: 0.9 }),
      makeCriteria({ min_profit_factor: 1.5 })
    );
    expect(result.passed).toBe(false);
    const failed = result.details.find((d) => d.gate === "min_profit_factor");
    expect(failed?.passed).toBe(false);
  });

  it("should check Sharpe ratio when specified", () => {
    const result = evaluateGates(
      makeMetrics({ sharpe_ratio: 0.5 }),
      makeCriteria({ min_sharpe: 1.0 })
    );
    expect(result.passed).toBe(false);
    const failed = result.details.find((d) => d.gate === "min_sharpe");
    expect(failed?.passed).toBe(false);
  });

  it("should skip Sharpe check when criteria is null", () => {
    const result = evaluateGates(
      makeMetrics({ sharpe_ratio: -1 }),
      makeCriteria({ min_sharpe: null })
    );
    // Should pass if all other criteria pass
    expect(result.details.find((d) => d.gate === "min_sharpe")).toBeUndefined();
    expect(result.passed).toBe(true);
  });

  it("should report all failed gates", () => {
    const result = evaluateGates(
      makeMetrics({ total_trades: 5, win_rate: 0.20, profit_factor: 0.5 }),
      makeCriteria()
    );
    expect(result.passed).toBe(false);
    const failedCount = result.details.filter((d) => !d.passed).length;
    expect(failedCount).toBeGreaterThanOrEqual(3);
  });

  it("should include actual values in details", () => {
    const metrics = makeMetrics({ win_rate: 0.60 });
    const result = evaluateGates(metrics, makeCriteria());
    const winRateCheck = result.details.find((d) => d.gate === "min_win_rate");
    expect(winRateCheck?.actual).toBe(0.60);
    expect(winRateCheck?.required).toBe(0.50);
  });
});
