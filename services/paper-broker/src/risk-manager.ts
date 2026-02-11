/**
 * Risk Manager for Paper Broker
 * Enforces position-level and account-level risk constraints.
 */
import { createLogger } from "../../shared/src/logger.js";
import type { Account, Order, Position } from "../../shared/src/types.js";
import { checkPDT, type PDTConfig } from "./pdt-limiter.js";

const log = createLogger("risk-manager");

export interface RiskConfig {
  maxRiskPerTrade: number;      // max cost for any single trade, default $100
  maxConcurrentPositions: number; // default 5
  maxSingleSymbolPct: number;   // max % of equity in one symbol, default 50
  pdtConfig: PDTConfig;
}

const DEFAULT_CONFIG: RiskConfig = {
  maxRiskPerTrade: 100,
  maxConcurrentPositions: 5,
  maxSingleSymbolPct: 50,
  pdtConfig: { maxDayTrades: 3, windowDays: 5 },
};

export interface RiskCheckResult {
  allowed: boolean;
  reason?: string;
}

/**
 * Check if an order passes all risk rules.
 */
export function checkOrderRisk(
  account: Account,
  order: Partial<Order>,
  openPositions: Position[],
  isDayTrade: boolean = false,
  config: Partial<RiskConfig> = {}
): RiskCheckResult {
  const cfg = { ...DEFAULT_CONFIG, ...config };
  const quantity = order.quantity ?? 1;
  const price = order.price ?? 0;
  const side = order.side ?? "buy";
  const symbol = order.symbol ?? "";

  // ─── 1. Buying Power Check ────────────────────────────────────────
  if (side === "buy") {
    const cost = price * quantity * 100; // options multiplier
    if (cost > account.buying_power) {
      log.warn("Risk reject: insufficient buying power", {
        cost,
        buying_power: account.buying_power,
      });
      return {
        allowed: false,
        reason: `Insufficient buying power: need $${cost.toFixed(2)}, have $${account.buying_power.toFixed(2)}`,
      };
    }
  }

  // ─── 2. Max Risk Per Trade ────────────────────────────────────────
  if (side === "buy") {
    const cost = price * quantity * 100;
    if (cost > cfg.maxRiskPerTrade) {
      log.warn("Risk reject: exceeds max risk per trade", {
        cost,
        max: cfg.maxRiskPerTrade,
      });
      return {
        allowed: false,
        reason: `Order cost $${cost.toFixed(2)} exceeds max risk per trade $${cfg.maxRiskPerTrade}`,
      };
    }
  }

  // ─── 3. Max Concurrent Positions ──────────────────────────────────
  if (side === "buy" && openPositions.length >= cfg.maxConcurrentPositions) {
    log.warn("Risk reject: max concurrent positions", {
      current: openPositions.length,
      max: cfg.maxConcurrentPositions,
    });
    return {
      allowed: false,
      reason: `Max concurrent positions reached (${openPositions.length}/${cfg.maxConcurrentPositions})`,
    };
  }

  // ─── 4. Symbol Concentration ──────────────────────────────────────
  if (side === "buy" && account.equity > 0) {
    const existingInSymbol = openPositions
      .filter((p) => p.symbol === symbol || p.underlying === symbol)
      .reduce((sum, p) => sum + (p.market_value ?? 0), 0);
    const newValue = price * quantity * 100;
    const totalInSymbol = existingInSymbol + newValue;
    const pctOfEquity = (totalInSymbol / account.equity) * 100;

    if (pctOfEquity > cfg.maxSingleSymbolPct) {
      log.warn("Risk reject: symbol concentration", {
        symbol,
        pctOfEquity: pctOfEquity.toFixed(1),
        max: cfg.maxSingleSymbolPct,
      });
      return {
        allowed: false,
        reason: `Symbol ${symbol} would be ${pctOfEquity.toFixed(1)}% of equity (max ${cfg.maxSingleSymbolPct}%)`,
      };
    }
  }

  // ─── 5. PDT Check ────────────────────────────────────────────────
  if (isDayTrade) {
    const pdtStatus = checkPDT(account.day_trades_history, cfg.pdtConfig);
    if (!pdtStatus.can_day_trade) {
      log.warn("Risk reject: PDT limit", {
        count: pdtStatus.day_trade_count,
        max: pdtStatus.max_allowed,
        nextExpiry: pdtStatus.next_expiry,
      });
      return {
        allowed: false,
        reason: `PDT limit reached: ${pdtStatus.day_trade_count}/${pdtStatus.max_allowed} day trades used. Next slot opens ${pdtStatus.next_expiry ?? "unknown"}`,
      };
    }
  }

  return { allowed: true };
}
