/**
 * Gate Evaluation — Checks if experiment metrics pass the gate criteria.
 * A strategy must pass all gates to become "approved" for production paper trading.
 */
import { createLogger } from "../../shared/src/logger.js";
import type { ExperimentMetrics, GateCriteria } from "../../shared/src/types.js";

const log = createLogger("strategy-lab:gates");

export interface GateResult {
  passed: boolean;
  details: GateCheckDetail[];
}

export interface GateCheckDetail {
  gate: string;
  required: number | null;
  actual: number;
  passed: boolean;
}

/**
 * Evaluate experiment metrics against gate criteria.
 * All applicable gates must pass for overall approval.
 */
export function evaluateGates(
  metrics: ExperimentMetrics,
  criteria: GateCriteria
): GateResult {
  const details: GateCheckDetail[] = [];

  // 1. Minimum trades
  details.push({
    gate: "min_trades",
    required: criteria.min_trades,
    actual: metrics.total_trades,
    passed: metrics.total_trades >= criteria.min_trades,
  });

  // 2. Minimum win rate
  details.push({
    gate: "min_win_rate",
    required: criteria.min_win_rate,
    actual: metrics.win_rate,
    passed: metrics.win_rate >= criteria.min_win_rate,
  });

  // 3. Maximum drawdown
  details.push({
    gate: "max_drawdown",
    required: criteria.max_drawdown,
    actual: metrics.max_drawdown,
    passed: metrics.max_drawdown <= criteria.max_drawdown,
  });

  // 4. Minimum profit factor
  details.push({
    gate: "min_profit_factor",
    required: criteria.min_profit_factor,
    actual: metrics.profit_factor,
    passed: metrics.profit_factor >= criteria.min_profit_factor,
  });

  // 5. Minimum Sharpe (optional)
  if (criteria.min_sharpe !== null && metrics.sharpe_ratio !== null) {
    details.push({
      gate: "min_sharpe",
      required: criteria.min_sharpe,
      actual: metrics.sharpe_ratio,
      passed: metrics.sharpe_ratio >= criteria.min_sharpe,
    });
  }

  const passed = details.every((d) => d.passed);

  if (!passed) {
    const failed = details.filter((d) => !d.passed).map((d) => d.gate);
    log.warn("Gate evaluation failed", { failed });
  } else {
    log.info("Gate evaluation passed", { checks: details.length });
  }

  return { passed, details };
}
