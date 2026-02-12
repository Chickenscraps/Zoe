/**
 * Trading Strategy Config — Browser-side schema, presets, and helpers.
 * Mirrors services/shared/src/strategy-config.ts but runs in the browser
 * (no node:crypto dependency).
 */

// ─── Config Shape ────────────────────────────────────────────────────────

export interface StrategyConfig {
  trading_enabled: boolean;
  risk: {
    risk_per_trade_pct: number;
    max_notional_exposure_pct: number;
  };
  signals: {
    min_signal_score: number;
    confirmations_required: number;
  };
  exits: {
    tp_pct: number;
    stop: {
      method: "ATR" | "percent";
      atr_mult?: number;
      stop_pct?: number;
    };
  };
  execution: {
    max_spread_pct_to_trade: number;
    limit_chase: {
      enabled: boolean;
      max_cross_pct: number;
      step_pct: number;
      steps: number;
    };
  };
  timing: {
    time_stop_hours: number;
    cooldown_minutes: number;
    cooldown_after_loss_multiplier: number;
  };
  gates: {
    vol_halt_24h_range: number;
    liquidity_min_score: number;
    max_trades_per_hour: number;
  };
  strategies: {
    bounce_enabled: boolean;
    trend_follow_enabled: boolean;
    mean_reversion_enabled: boolean;
    weights: {
      bounce: number;
      trend_follow: number;
      mean_reversion: number;
    };
  };
}

// ─── Validation Bounds (for UI) ──────────────────────────────────────────

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
    description: "Low risk, high signal threshold, tight exposure limits.",
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
    description: "Default settings. Good risk/reward balance.",
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
    description: "Higher risk, lower signal bar, wider exposure.",
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

// ─── Validation ──────────────────────────────────────────────────────────

export interface ValidationError {
  path: string;
  message: string;
}

/** Validate a config value against its dial bounds. */
function validateBound(path: string, value: number): ValidationError | null {
  const bounds = DIAL_BOUNDS[path];
  if (!bounds) return null;
  if (value < bounds.min) return { path, message: `${bounds.label} must be at least ${bounds.min}` };
  if (value > bounds.max) return { path, message: `${bounds.label} must be at most ${bounds.max}` };
  return null;
}

/** Validate an entire config. Returns array of errors (empty = valid). */
export function validateConfig(config: StrategyConfig): ValidationError[] {
  const errors: ValidationError[] = [];

  errors.push(...[
    validateBound("risk.risk_per_trade_pct", config.risk.risk_per_trade_pct),
    validateBound("risk.max_notional_exposure_pct", config.risk.max_notional_exposure_pct),
    validateBound("signals.min_signal_score", config.signals.min_signal_score),
    validateBound("signals.confirmations_required", config.signals.confirmations_required),
    validateBound("exits.tp_pct", config.exits.tp_pct),
    config.exits.stop.atr_mult != null
      ? validateBound("exits.stop.atr_mult", config.exits.stop.atr_mult)
      : null,
    validateBound("execution.max_spread_pct_to_trade", config.execution.max_spread_pct_to_trade),
    validateBound("execution.limit_chase.max_cross_pct", config.execution.limit_chase.max_cross_pct),
    validateBound("timing.time_stop_hours", config.timing.time_stop_hours),
    validateBound("timing.cooldown_minutes", config.timing.cooldown_minutes),
    validateBound("timing.cooldown_after_loss_multiplier", config.timing.cooldown_after_loss_multiplier),
    validateBound("gates.vol_halt_24h_range", config.gates.vol_halt_24h_range),
    validateBound("gates.max_trades_per_hour", config.gates.max_trades_per_hour),
  ].filter((e): e is ValidationError => e !== null));

  // Strategy weights should sum to ~1.0 (if any strategy is enabled)
  const w = config.strategies.weights;
  const enabledSum =
    (config.strategies.bounce_enabled ? w.bounce : 0) +
    (config.strategies.trend_follow_enabled ? w.trend_follow : 0) +
    (config.strategies.mean_reversion_enabled ? w.mean_reversion : 0);
  if (enabledSum > 0 && Math.abs(enabledSum - 1.0) > 0.01) {
    errors.push({
      path: "strategies.weights",
      message: `Enabled strategy weights should sum to 1.0 (currently ${enabledSum.toFixed(2)})`,
    });
  }

  return errors;
}

// ─── Helpers ─────────────────────────────────────────────────────────────

/** Browser-compatible checksum via SubtleCrypto. */
export async function configChecksum(config: StrategyConfig): Promise<string> {
  const canonical = JSON.stringify(config, Object.keys(config).sort());
  const encoded = new TextEncoder().encode(canonical);
  const hashBuf = await crypto.subtle.digest("SHA-256", encoded);
  const hashArr = Array.from(new Uint8Array(hashBuf));
  return hashArr.map(b => b.toString(16).padStart(2, "0")).join("").slice(0, 16);
}

/** Compute diff between two configs. */
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

/** Get nested value by dot-path. */
export function getConfigValue(config: StrategyConfig, path: string): unknown {
  const parts = path.split(".");
  let current: unknown = config;
  for (const part of parts) {
    if (current === null || current === undefined || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

/** Set nested value by dot-path. Returns new config (immutable). */
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

/** High-risk dials that need extra LIVE confirmation. */
export const HIGH_RISK_DIALS = new Set([
  "trading_enabled",
  "risk.risk_per_trade_pct",
  "risk.max_notional_exposure_pct",
]);

/** Format a dial value for display. */
export function formatDialValue(path: string, value: unknown): string {
  const bounds = DIAL_BOUNDS[path];
  if (bounds === undefined) {
    if (typeof value === "boolean") return value ? "ON" : "OFF";
    return String(value);
  }
  const num = Number(value);
  switch (bounds.format) {
    case "percent": return (num * 100).toFixed(1) + "%";
    case "multiplier": return num.toFixed(1) + "x";
    case "hours": return num + "h";
    case "minutes": return num + "m";
    default: return String(num);
  }
}
