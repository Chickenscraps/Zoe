/**
 * Strategy Registry — CRUD for strategy definitions with versioning.
 * Strategies must pass gate criteria before becoming "approved".
 */
import { createLogger } from "../../shared/src/logger.js";
import { getDb, auditLog } from "../../shared/src/db.js";
import type {
  StrategyRegistryEntry,
  StrategyStatus,
  GateCriteria,
} from "../../shared/src/types.js";

const log = createLogger("strategy-lab:registry");

const DEFAULT_GATE_CRITERIA: GateCriteria = {
  min_trades: 30,
  min_win_rate: 0.50,
  max_drawdown: 0.20,
  min_profit_factor: 1.5,
  min_sharpe: null,
};

export class StrategyRegistry {
  /**
   * Register a new candidate strategy.
   */
  async register(
    name: string,
    description: string,
    parameters: Record<string, unknown> = {},
    gateCriteria: Partial<GateCriteria> = {}
  ): Promise<StrategyRegistryEntry | null> {
    try {
      const db = getDb();
      const gates = { ...DEFAULT_GATE_CRITERIA, ...gateCriteria };

      const { data, error } = await db
        .from("strategy_registry")
        .insert({
          name,
          version: "1.0.0",
          status: "candidate" as StrategyStatus,
          description,
          parameters,
          gate_criteria: gates,
        })
        .select()
        .single();

      if (error) {
        log.error("Failed to register strategy", { name, error: error.message });
        return null;
      }

      await auditLog("strategy_registered", { name, id: data.id });
      log.info("Strategy registered", { name, id: data.id });
      return data as unknown as StrategyRegistryEntry;
    } catch (e) {
      log.error("register error", { error: String(e) });
      return null;
    }
  }

  /**
   * Update a strategy's status.
   */
  async updateStatus(id: string, status: StrategyStatus): Promise<boolean> {
    try {
      const db = getDb();
      const { error } = await db
        .from("strategy_registry")
        .update({ status, updated_at: new Date().toISOString() })
        .eq("id", id);

      if (error) {
        log.error("Failed to update strategy status", { id, error: error.message });
        return false;
      }

      await auditLog("strategy_status_changed", { id, status });
      log.info("Strategy status updated", { id, status });
      return true;
    } catch (e) {
      log.error("updateStatus error", { error: String(e) });
      return false;
    }
  }

  /**
   * Bump the version of a strategy (e.g., after parameter changes).
   */
  async bumpVersion(id: string, newVersion: string): Promise<boolean> {
    try {
      const db = getDb();
      const { error } = await db
        .from("strategy_registry")
        .update({ version: newVersion, updated_at: new Date().toISOString() })
        .eq("id", id);

      if (error) return false;

      await auditLog("strategy_version_bumped", { id, version: newVersion });
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Get all strategies with a given status.
   */
  async getByStatus(status: StrategyStatus): Promise<StrategyRegistryEntry[]> {
    try {
      const db = getDb();
      const { data, error } = await db
        .from("strategy_registry")
        .select("*")
        .eq("status", status)
        .order("created_at", { ascending: false });

      if (error) return [];
      return (data ?? []) as unknown as StrategyRegistryEntry[];
    } catch {
      return [];
    }
  }

  /**
   * Get a single strategy by ID.
   */
  async getById(id: string): Promise<StrategyRegistryEntry | null> {
    try {
      const db = getDb();
      const { data, error } = await db
        .from("strategy_registry")
        .select("*")
        .eq("id", id)
        .single();

      if (error || !data) return null;
      return data as unknown as StrategyRegistryEntry;
    } catch {
      return null;
    }
  }
}
