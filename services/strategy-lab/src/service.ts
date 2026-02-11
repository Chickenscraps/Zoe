/**
 * StrategyLabService — Orchestrates strategy registration, experiments, and promotion.
 * High-level API for the strategy lifecycle:
 *   1. Register candidate strategy
 *   2. Run walk-forward experiment
 *   3. Evaluate gates
 *   4. Promote to "approved" if gates pass
 */
import { createLogger } from "../../shared/src/logger.js";
import type { StrategyRegistryEntry, ExperimentRun } from "../../shared/src/types.js";
import { StrategyRegistry } from "./registry.js";
import { ExperimentRunner, type ExperimentConfig } from "./experiment-runner.js";
import type { GateResult } from "./gates.js";

const log = createLogger("strategy-lab");

export class StrategyLabService {
  readonly registry: StrategyRegistry;
  readonly runner: ExperimentRunner;

  constructor(experimentConfig: Partial<ExperimentConfig> = {}) {
    this.registry = new StrategyRegistry();
    this.runner = new ExperimentRunner(experimentConfig);
    log.info("StrategyLabService initialized");
  }

  /**
   * Full lifecycle: run experiment → evaluate gates → auto-promote if passed.
   */
  async evaluateStrategy(strategyId: string): Promise<{
    experiment: ExperimentRun;
    gateResult: GateResult;
    promoted: boolean;
  } | null> {
    // 1. Load strategy
    const strategy = await this.registry.getById(strategyId);
    if (!strategy) {
      log.error("Strategy not found", { strategyId });
      return null;
    }

    if (strategy.status !== "candidate") {
      log.warn("Strategy is not a candidate", { strategyId, status: strategy.status });
      return null;
    }

    // 2. Run experiment
    const result = await this.runner.runExperiment(strategy);
    if (!result) return null;

    // 3. Auto-promote if gates pass
    let promoted = false;
    if (result.gateResult.passed) {
      promoted = await this.registry.updateStatus(strategyId, "approved");
      if (promoted) {
        log.info("Strategy promoted to approved", {
          name: strategy.name,
          version: strategy.version,
        });
      }
    }

    return {
      experiment: result.run,
      gateResult: result.gateResult,
      promoted,
    };
  }

  /**
   * Get all candidate strategies that need evaluation.
   */
  async getCandidates(): Promise<StrategyRegistryEntry[]> {
    return this.registry.getByStatus("candidate");
  }

  /**
   * Get all approved strategies (ready for production paper trading).
   */
  async getApproved(): Promise<StrategyRegistryEntry[]> {
    return this.registry.getByStatus("approved");
  }

  /**
   * Retire a strategy (remove from production without deleting history).
   */
  async retireStrategy(strategyId: string): Promise<boolean> {
    return this.registry.updateStatus(strategyId, "retired");
  }
}
