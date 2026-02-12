/**
 * Zoe V4 — Trading Strategy Config ("Dials")
 *
 * Defines the canonical shape, validation bounds, and preset profiles
 * for the runtime trading configuration. Used by:
 *   - Dashboard (Settings page)
 *   - Bot (ConfigLoader hot-reload)
 *   - Audit log (diff computation)
 */
import { z } from "zod";
import { createHash } from "node:crypto";

// ─── Zod Schema ──────────────────────────────────────────────────────────

export const strategyConfigSchema = z.object({
  trading_enabled: z.boolean(),

  risk: z.object({
    risk_per_trade_pct: z.number().min(0.002).max(0.05),
    max_notional_exposure_pct: z.number().min(0.05).max(1.0),
  }),

  signals: z.object({
    min_signal_score: z.number().int().min(50).max(90),
    confirmations_required: z.number().int().min(1).max(3),
  }),

  exits: z.object({
    tp_pct: z.number().min(0.005).max(0.10),
    stop: z.object({
      method: z.enum(["ATR", "percent"]),
      atr_mult: z.number().min(0.5).max(3.0).optional(),
      stop_pct: z.number().min(0.005).max(0.10).optional(),
    }),
  }),

  execution: z.object({
    max_spread_pct_to_trade: z.number().min(0.0005).max(0.01),
    limit_chase: z.object({
      enabled: z.boolean(),
      max_cross_pct: z.number().min(0.0005).max(0.01),
      step_pct: z.number().min(0.0001).max(0.005),
      steps: z.number().int().min(1).max(10),
    }),
  }),

  timing: z.object({
    time_stop_hours: z.number().min(1).max(168),
    cooldown_minutes: z.number().min(0).max(120),
    cooldown_after_loss_multiplier: z.number().min(1.0).max(5.0),
  }),

  gates: z.object({
    vol_halt_24h_range: z.number().min(0.01).max(0.20),
    liquidity_min_score: z.number().min(0).max(1e12),
    max_trades_per_hour: z.number().int().min(1).max(20),
  }),

  strategies: z.object({
    bounce_enabled: z.boolean(),
    trend_follow_enabled: z.boolean(),
    mean_reversion_enabled: z.boolean(),
    weights: z.object({
      bounce: z.number().min(0).max(1),
      trend_follow: z.number().min(0).max(1),
      mean_reversion: z.number().min(0).max(1),
    }),
  }),
});

export type StrategyConfig = z.infer<typeof strategyConfigSchema>;

// ─── Validation Bounds (for UI display) ──────────────────────────────────

export interface DialBounds {
  min: number;
  max: number;
  step: number;
  label: string;
  tooltip: string;
  unit: string;
  format: "percent" | "number" | "multiplier" | "currency" | "hours" | "minutes";
}

export const DIAL_BOUNDS: Record<string, DialBounds> = {
  "risk.risk_per_trade_pct": {
    min: 0.002, max: 0.05, step: 0.001,
    label: "Risk Per Trade",
    tooltip: "Max portfolio % risked per trade. Lower = safer, slower growth. Higher = more aggressive.",
    unit: "%", format: "percent",
  },
  "risk.max_notional_exposure_pct": {
    min: 0.05, max: 1.0, step: 0.05,
    label: "Max Exposure",
    tooltip: "Portfolio heat cap — total notional across all open positions as % of equity.",
    unit: "%", format: "percent",
  },
  "signals.min_signal_score": {
    min: 50, max: 90, step: 1,
    label: "Min Signal Score",
    tooltip: "Minimum composite signal score (0-100) to consider a trade. Higher = pickier.",
    unit: "", format: "number",
  },
  "signals.confirmations_required": {
    min: 1, max: 3, step: 1,
    label: "Confirmations Required",
    tooltip: "Number of confirming signals needed before entry. More = safer but slower.",
    unit: "", format: "number",
  },
  "exits.tp_pct": {
    min: 0.005, max: 0.10, step: 0.005,
    label: "Take Profit %",
    tooltip: "Target profit percentage from entry price.",
    unit: "%", format: "percent",
  },
  "exits.stop.atr_mult": {
    min: 0.5, max: 3.0, step: 0.1,
    label: "Stop ATR Multiple",
    tooltip: "Stop-loss width as multiple of ATR. Tighter = less risk but more stopped out.",
    unit: "x", format: "multiplier",
  },
  "execution.max_spread_pct_to_trade": {
    min: 0.0005, max: 0.01, step: 0.0005,
    label: "Max Spread",
    tooltip: "Will not trade if bid-ask spread exceeds this %. Guards against illiquid conditions.",
    unit: "%", format: "percent",
  },
  "execution.limit_chase.max_cross_pct": {
    min: 0.0005, max: 0.01, step: 0.0005,
    label: "Max Chase Cross",
    tooltip: "How aggressively the limit order can cross the spread. Higher = fills faster but costs more.",
    unit: "%", format: "percent",
  },
  "timing.time_stop_hours": {
    min: 1, max: 168, step: 1,
    label: "Time Stop",
    tooltip: "Close position if not profitable after this many hours.",
    unit: "hrs", format: "hours",
  },
  "timing.cooldown_minutes": {
    min: 0, max: 120, step: 5,
    label: "Cooldown",
    tooltip: "Minutes to wait between trades (prevents overtrading).",
    unit: "min", format: "minutes",
  },
  "timing.cooldown_after_loss_multiplier": {
    min: 1.0, max: 5.0, step: 0.5,
    label: "Loss Cooldown Multiplier",
    tooltip: "Multiply cooldown by this after a loss. Higher = more cautious after losing.",
    unit: "x", format: "multiplier",
  },
  "gates.vol_halt_24h_range": {
    min: 0.01, max: 0.20, step: 0.01,
    label: "Volatility Halt Range",
    tooltip: "Halt trading if 24h price range exceeds this %. Protects against extreme moves.",
    unit: "%", format: "percent",
  },
  "gates.max_trades_per_hour": {
    min: 1, max: 20, step: 1,
    label: "Max Trades/Hour",
    tooltip: "Rate limiter to prevent runaway trading loops.",
    unit: "", format: "number",
  },
};

// ─── Preset Profiles ────────────────────────────────────────────────────

export const PRESET_PROFILES: Record<string, { label: string; description: string; config: StrategyConfig }> = {
  conservative: {
    label: "Conservative",
    description: "Low risk, high signal threshold, tight exposure limits. Best for capital preservation.",
    config: {
      trading_enabled: true,
      risk: { risk_per_trade_pct: 0.01, max_notional_exposure_pct: 0.20 },
      signals: { min_signal_score: 80, confirmations_required: 3 },
      exits: { tp_pct: 0.03, stop: { method: "ATR", atr_mult: 1.0 } },
      execution: {
        max_spread_pct_to_trade: 0.002,
        limit_chase: { enabled: true, max_cross_pct: 0.001, step_pct: 0.0003, steps: 2 },
      },
      timing: { time_stop_hours: 8, cooldown_minutes: 30, cooldown_after_loss_multiplier: 3.0 },
      gates: { vol_halt_24h_range: 0.03, liquidity_min_score: 5e7, max_trades_per_hour: 3 },
      strategies: {
        bounce_enabled: true, trend_follow_enabled: false, mean_reversion_enabled: true,
        weights: { bounce: 0.6, trend_follow: 0, mean_reversion: 0.4 },
      },
    },
  },
  balanced: {
    label: "Balanced",
    description: "Default settings. Good risk/reward balance for steady growth.",
    config: {
      trading_enabled: true,
      risk: { risk_per_trade_pct: 0.02, max_notional_exposure_pct: 0.40 },
      signals: { min_signal_score: 70, confirmations_required: 2 },
      exits: { tp_pct: 0.045, stop: { method: "ATR", atr_mult: 1.5 } },
      execution: {
        max_spread_pct_to_trade: 0.003,
        limit_chase: { enabled: true, max_cross_pct: 0.002, step_pct: 0.0005, steps: 3 },
      },
      timing: { time_stop_hours: 12, cooldown_minutes: 15, cooldown_after_loss_multiplier: 2.0 },
      gates: { vol_halt_24h_range: 0.05, liquidity_min_score: 1e7, max_trades_per_hour: 6 },
      strategies: {
        bounce_enabled: true, trend_follow_enabled: false, mean_reversion_enabled: true,
        weights: { bounce: 0.6, trend_follow: 0, mean_reversion: 0.4 },
      },
    },
  },
  aggressive: {
    label: "Aggressive",
    description: "Higher risk tolerance, lower signal bar, wider exposure. For experienced operators.",
    config: {
      trading_enabled: true,
      risk: { risk_per_trade_pct: 0.04, max_notional_exposure_pct: 0.70 },
      signals: { min_signal_score: 55, confirmations_required: 1 },
      exits: { tp_pct: 0.06, stop: { method: "ATR", atr_mult: 2.0 } },
      execution: {
        max_spread_pct_to_trade: 0.005,
        limit_chase: { enabled: true, max_cross_pct: 0.004, step_pct: 0.001, steps: 4 },
      },
      timing: { time_stop_hours: 24, cooldown_minutes: 5, cooldown_after_loss_multiplier: 1.5 },
      gates: { vol_halt_24h_range: 0.08, liquidity_min_score: 5e6, max_trades_per_hour: 10 },
      strategies: {
        bounce_enabled: true, trend_follow_enabled: true, mean_reversion_enabled: true,
        weights: { bounce: 0.4, trend_follow: 0.3, mean_reversion: 0.3 },
      },
    },
  },
};

// ─── Helpers ─────────────────────────────────────────────────────────────

/**
 * Validate a config object. Returns parsed config or throws.
 */
export function validateConfig(raw: unknown): StrategyConfig {
  return strategyConfigSchema.parse(raw);
}

/**
 * Safe validate — returns result object, never throws.
 */
export function safeValidateConfig(raw: unknown): z.SafeParseReturnType<unknown, StrategyConfig> {
  return strategyConfigSchema.safeParse(raw);
}

/**
 * Compute SHA-256 checksum of a config JSON for integrity verification.
 * Uses a deep-sorting replacer to ensure deterministic serialization.
 */
export function configChecksum(config: StrategyConfig): string {
  const canonical = JSON.stringify(config, (_key, value) => {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      const sorted: Record<string, unknown> = {};
      for (const k of Object.keys(value).sort()) {
        sorted[k] = (value as Record<string, unknown>)[k];
      }
      return sorted;
    }
    return value as unknown;
  });
  return createHash("sha256").update(canonical).digest("hex").slice(0, 16);
}

/**
 * Compute a diff between two config objects.
 * Returns an object with only the changed keys and their old/new values.
 */
export function configDiff(
  prev: StrategyConfig,
  next: StrategyConfig
): Record<string, { old: unknown; new: unknown }> {
  const diffs: Record<string, { old: unknown; new: unknown }> = {};

  function walk(p: Record<string, unknown>, n: Record<string, unknown>, prefix: string) {
    const allKeys = new Set([...Object.keys(p), ...Object.keys(n)]);
    for (const key of allKeys) {
      const path = prefix ? `${prefix}.${key}` : key;
      const pv = p[key];
      const nv = n[key];
      if (typeof pv === "object" && pv !== null && typeof nv === "object" && nv !== null && !Array.isArray(pv)) {
        walk(pv as Record<string, unknown>, nv as Record<string, unknown>, path);
      } else if (JSON.stringify(pv) !== JSON.stringify(nv)) {
        diffs[path] = { old: pv, new: nv };
      }
    }
  }

  walk(prev as unknown as Record<string, unknown>, next as unknown as Record<string, unknown>, "");
  return diffs;
}

/**
 * Get a nested value from config by dot-path.
 */
export function getConfigValue(config: StrategyConfig, path: string): unknown {
  const parts = path.split(".");
  let current: unknown = config;
  for (const part of parts) {
    if (current === null || current === undefined || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

/**
 * Set a nested value in config by dot-path. Returns a new config object (immutable).
 */
export function setConfigValue(config: StrategyConfig, path: string, value: unknown): StrategyConfig {
  const clone = JSON.parse(JSON.stringify(config)) as Record<string, unknown>;
  const parts = path.split(".");
  let current = clone;
  for (let i = 0; i < parts.length - 1; i++) {
    current = current[parts[i]] as Record<string, unknown>;
  }
  current[parts[parts.length - 1]] = value;
  return clone as unknown as StrategyConfig;
}

/**
 * High-risk dials that require extra confirmation in LIVE mode.
 */
export const HIGH_RISK_DIALS = new Set([
  "trading_enabled",
  "risk.risk_per_trade_pct",
  "risk.max_notional_exposure_pct",
]);
