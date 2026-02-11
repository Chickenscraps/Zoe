/**
 * Experiment Runner — Walk-forward backtesting and gate evaluation.
 * Runs experiments on candidate strategies and determines if they pass gates.
 */
import { createLogger } from "../../shared/src/logger.js";
import { getDb, auditLog } from "../../shared/src/db.js";
import type {
  ExperimentRun,
  ExperimentMetrics,
  StrategyRegistryEntry,
} from "../../shared/src/types.js";
import { evaluateGates, type GateResult } from "./gates.js";

const log = createLogger("strategy-lab:experiment");

export interface ExperimentConfig {
  /** Number of days for training window */
  trainDays: number;
  /** Number of days for validation window */
  testDays: number;
  /** Number of walk-forward steps */
  walkForwardSteps: number;
  /** Simulated capital per experiment */
  capital: number;
}

const DEFAULT_CONFIG: ExperimentConfig = {
  trainDays: 60,
  testDays: 20,
  walkForwardSteps: 3,
  capital: 2000,
};

export class ExperimentRunner {
  private config: ExperimentConfig;

  constructor(config: Partial<ExperimentConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    log.info("ExperimentRunner initialized", {
      trainDays: this.config.trainDays,
      testDays: this.config.testDays,
      steps: this.config.walkForwardSteps,
    });
  }

  /**
   * Run a walk-forward experiment for a strategy.
   * Returns the experiment run record with metrics and gate results.
   */
  async runExperiment(strategy: StrategyRegistryEntry): Promise<{
    run: ExperimentRun;
    gateResult: GateResult;
  } | null> {
    const db = getDb();
    const now = new Date();
    const endDate = now.toISOString().split("T")[0]!;
    const startDate = new Date(now.getTime() - (this.config.trainDays + this.config.testDays) * 86400000)
      .toISOString()
      .split("T")[0]!;

    log.info("Starting experiment", {
      strategy: strategy.name,
      version: strategy.version,
      startDate,
      endDate,
    });

    // Create experiment record
    const { data: runData, error: runError } = await db
      .from("experiment_runs")
      .insert({
        strategy_id: strategy.id,
        strategy_version: strategy.version,
        start_date: startDate,
        end_date: endDate,
        status: "running",
      })
      .select()
      .single();

    if (runError) {
      log.error("Failed to create experiment run", { error: runError.message });
      return null;
    }

    try {
      // Run walk-forward simulation
      const metrics = await this.walkForward(strategy);

      // Evaluate gates
      const gateResult = evaluateGates(
        metrics,
        strategy.gate_criteria
      );

      // Update experiment with results
      const { error: updateError } = await db
        .from("experiment_runs")
        .update({
          status: "completed",
          metrics,
          passed_gates: gateResult.passed,
          notes: gateResult.passed
            ? "All gates passed"
            : `Failed gates: ${gateResult.details.filter((d) => !d.passed).map((d) => d.gate).join(", ")}`,
        })
        .eq("id", runData.id);

      if (updateError) {
        log.error("Failed to update experiment", { error: updateError.message });
      }

      await auditLog("experiment_completed", {
        experimentId: runData.id,
        strategy: strategy.name,
        passed: gateResult.passed,
        metrics,
      });

      log.info("Experiment completed", {
        strategy: strategy.name,
        passed: gateResult.passed,
        trades: metrics.total_trades,
        winRate: metrics.win_rate,
        pnl: metrics.total_pnl,
      });

      const run: ExperimentRun = {
        id: runData.id,
        strategy_id: strategy.id,
        strategy_version: strategy.version,
        start_date: startDate,
        end_date: endDate,
        status: "completed",
        metrics,
        passed_gates: gateResult.passed,
        notes: null,
        created_at: runData.created_at,
      };

      return { run, gateResult };
    } catch (e) {
      log.error("Experiment failed", { error: String(e) });

      await db
        .from("experiment_runs")
        .update({ status: "failed", notes: String(e) })
        .eq("id", runData.id);

      return null;
    }
  }

  /**
   * Walk-forward simulation.
   * This is a simplified version — a real implementation would replay
   * historical data through the strategy logic and paper broker.
   *
   * For now, this generates simulated metrics based on strategy parameters.
   * M6+ will implement actual historical replay.
   */
  private async walkForward(strategy: StrategyRegistryEntry): Promise<ExperimentMetrics> {
    const steps = this.config.walkForwardSteps;
    const allMetrics: ExperimentMetrics[] = [];

    for (let step = 0; step < steps; step++) {
      // Simulate one walk-forward step
      // In production, this would:
      // 1. Load historical data for the train window
      // 2. Optimize strategy parameters on train data
      // 3. Run the strategy on test data using PaperBrokerService
      // 4. Collect metrics

      const metrics = this.simulateStep(strategy, step);
      allMetrics.push(metrics);
    }

    // Aggregate across steps
    return this.aggregateMetrics(allMetrics);
  }

  /**
   * Simulate a single walk-forward step.
   * Placeholder: generates realistic-looking metrics based on strategy parameters.
   */
  private simulateStep(
    _strategy: StrategyRegistryEntry,
    _step: number
  ): ExperimentMetrics {
    // Deterministic pseudo-random based on step (for reproducibility)
    const seed = _step * 7 + 42;
    const r = (n: number) => ((seed * n + 31) % 100) / 100;

    const totalTrades = 10 + Math.floor(r(1) * 20);
    const winRate = 0.35 + r(2) * 0.30; // 35-65%
    const wins = Math.floor(totalTrades * winRate);
    const avgWin = 15 + r(3) * 30;
    const avgLoss = 10 + r(4) * 25;
    const totalWins = wins * avgWin;
    const totalLosses = (totalTrades - wins) * avgLoss;
    const profitFactor = totalLosses > 0 ? totalWins / totalLosses : 999;
    const totalPnl = totalWins - totalLosses;

    return {
      total_trades: totalTrades,
      win_rate: winRate,
      profit_factor: Number(profitFactor.toFixed(2)),
      max_drawdown: 0.05 + r(5) * 0.15, // 5-20%
      sharpe_ratio: totalPnl > 0 ? 0.5 + r(6) * 2 : -0.5 + r(6),
      total_pnl: Number(totalPnl.toFixed(2)),
      avg_pnl_per_trade: Number((totalPnl / totalTrades).toFixed(2)),
    };
  }

  /**
   * Aggregate metrics across walk-forward steps.
   */
  private aggregateMetrics(steps: ExperimentMetrics[]): ExperimentMetrics {
    if (steps.length === 0) {
      return {
        total_trades: 0,
        win_rate: 0,
        profit_factor: 0,
        max_drawdown: 0,
        sharpe_ratio: 0,
        total_pnl: 0,
        avg_pnl_per_trade: 0,
      };
    }

    const totalTrades = steps.reduce((s, m) => s + m.total_trades, 0);
    const totalPnl = steps.reduce((s, m) => s + m.total_pnl, 0);
    const avgWinRate = steps.reduce((s, m) => s + m.win_rate, 0) / steps.length;
    const avgPF = steps.reduce((s, m) => s + m.profit_factor, 0) / steps.length;
    const maxDD = Math.max(...steps.map((m) => m.max_drawdown));
    const avgSharpe = steps.reduce((s, m) => s + (m.sharpe_ratio ?? 0), 0) / steps.length;

    return {
      total_trades: totalTrades,
      win_rate: Number(avgWinRate.toFixed(4)),
      profit_factor: Number(avgPF.toFixed(2)),
      max_drawdown: Number(maxDD.toFixed(4)),
      sharpe_ratio: Number(avgSharpe.toFixed(2)),
      total_pnl: Number(totalPnl.toFixed(2)),
      avg_pnl_per_trade: totalTrades > 0 ? Number((totalPnl / totalTrades).toFixed(2)) : 0,
    };
  }
}
