/**
 * Tests for strategy config validation, versioning, and diff computation.
 */
import { describe, it, expect } from "vitest";
import {
  validateConfig,
  safeValidateConfig,
  configChecksum,
  configDiff,
  getConfigValue,
  setConfigValue,
  PRESET_PROFILES,
  type StrategyConfig,
} from "../../services/shared/src/strategy-config.js";

// ─── Helpers ─────────────────────────────────────────────────────────────

function balancedConfig(): StrategyConfig {
  return JSON.parse(JSON.stringify(PRESET_PROFILES.balanced.config));
}

// ─── Validation Tests ───────────────────────────────────────────────────

describe("strategy config validation", () => {
  it("should accept a valid balanced config", () => {
    const cfg = balancedConfig();
    expect(() => validateConfig(cfg)).not.toThrow();
  });

  it("should accept all preset profiles", () => {
    for (const [key, profile] of Object.entries(PRESET_PROFILES)) {
      expect(() => validateConfig(profile.config), `preset ${key} should be valid`).not.toThrow();
    }
  });

  it("should reject risk_per_trade_pct below minimum (0.002)", () => {
    const cfg = balancedConfig();
    cfg.risk.risk_per_trade_pct = 0.001;
    const result = safeValidateConfig(cfg);
    expect(result.success).toBe(false);
  });

  it("should reject risk_per_trade_pct above maximum (0.05)", () => {
    const cfg = balancedConfig();
    cfg.risk.risk_per_trade_pct = 0.10;
    const result = safeValidateConfig(cfg);
    expect(result.success).toBe(false);
  });

  it("should reject max_notional_exposure_pct above 1.0", () => {
    const cfg = balancedConfig();
    cfg.risk.max_notional_exposure_pct = 1.5;
    const result = safeValidateConfig(cfg);
    expect(result.success).toBe(false);
  });

  it("should reject min_signal_score below 50", () => {
    const cfg = balancedConfig();
    cfg.signals.min_signal_score = 30;
    const result = safeValidateConfig(cfg);
    expect(result.success).toBe(false);
  });

  it("should reject min_signal_score above 90", () => {
    const cfg = balancedConfig();
    cfg.signals.min_signal_score = 95;
    const result = safeValidateConfig(cfg);
    expect(result.success).toBe(false);
  });

  it("should reject confirmations_required above 3", () => {
    const cfg = balancedConfig();
    cfg.signals.confirmations_required = 5;
    const result = safeValidateConfig(cfg);
    expect(result.success).toBe(false);
  });

  it("should reject tp_pct above 0.10", () => {
    const cfg = balancedConfig();
    cfg.exits.tp_pct = 0.20;
    const result = safeValidateConfig(cfg);
    expect(result.success).toBe(false);
  });

  it("should reject stop_atr_mult above 3.0", () => {
    const cfg = balancedConfig();
    cfg.exits.stop.atr_mult = 5.0;
    const result = safeValidateConfig(cfg);
    expect(result.success).toBe(false);
  });

  it("should reject max_spread_pct_to_trade above 0.01", () => {
    const cfg = balancedConfig();
    cfg.execution.max_spread_pct_to_trade = 0.05;
    const result = safeValidateConfig(cfg);
    expect(result.success).toBe(false);
  });

  it("should reject missing trading_enabled field", () => {
    const cfg = balancedConfig() as Record<string, unknown>;
    delete cfg["trading_enabled"];
    const result = safeValidateConfig(cfg);
    expect(result.success).toBe(false);
  });

  it("should accept edge values at boundaries", () => {
    const cfg = balancedConfig();
    cfg.risk.risk_per_trade_pct = 0.002; // minimum
    cfg.risk.max_notional_exposure_pct = 1.0; // maximum
    cfg.signals.min_signal_score = 50; // minimum
    cfg.signals.confirmations_required = 3; // maximum
    expect(() => validateConfig(cfg)).not.toThrow();
  });
});

// ─── Checksum Tests ─────────────────────────────────────────────────────

describe("config checksum", () => {
  it("should return consistent checksum for same config", () => {
    const cfg = balancedConfig();
    const hash1 = configChecksum(cfg);
    const hash2 = configChecksum(cfg);
    expect(hash1).toBe(hash2);
  });

  it("should return different checksum for different config", () => {
    const cfg1 = balancedConfig();
    const cfg2 = balancedConfig();
    cfg2.risk.risk_per_trade_pct = 0.03;
    const hash1 = configChecksum(cfg1);
    const hash2 = configChecksum(cfg2);
    expect(hash1).not.toBe(hash2);
  });

  it("should return a 16-char hex string", () => {
    const cfg = balancedConfig();
    const hash = configChecksum(cfg);
    expect(hash).toMatch(/^[0-9a-f]{16}$/);
  });
});

// ─── Diff Tests ─────────────────────────────────────────────────────────

describe("config diff", () => {
  it("should return empty diff for identical configs", () => {
    const cfg = balancedConfig();
    const diff = configDiff(cfg, cfg);
    expect(Object.keys(diff)).toHaveLength(0);
  });

  it("should detect single field change", () => {
    const prev = balancedConfig();
    const next = balancedConfig();
    next.risk.risk_per_trade_pct = 0.03;
    const diff = configDiff(prev, next);
    expect(diff).toHaveProperty("risk.risk_per_trade_pct");
    expect(diff["risk.risk_per_trade_pct"].old).toBe(0.02);
    expect(diff["risk.risk_per_trade_pct"].new).toBe(0.03);
  });

  it("should detect multiple changes", () => {
    const prev = balancedConfig();
    const next = balancedConfig();
    next.risk.risk_per_trade_pct = 0.03;
    next.signals.min_signal_score = 75;
    next.exits.tp_pct = 0.05;
    const diff = configDiff(prev, next);
    expect(Object.keys(diff)).toHaveLength(3);
  });

  it("should detect boolean change", () => {
    const prev = balancedConfig();
    const next = balancedConfig();
    next.trading_enabled = false;
    const diff = configDiff(prev, next);
    expect(diff).toHaveProperty("trading_enabled");
    expect(diff["trading_enabled"].old).toBe(true);
    expect(diff["trading_enabled"].new).toBe(false);
  });

  it("should detect nested object changes", () => {
    const prev = balancedConfig();
    const next = balancedConfig();
    next.execution.limit_chase.max_cross_pct = 0.005;
    const diff = configDiff(prev, next);
    expect(diff).toHaveProperty("execution.limit_chase.max_cross_pct");
  });
});

// ─── getConfigValue / setConfigValue Tests ──────────────────────────────

describe("config path helpers", () => {
  it("getConfigValue should retrieve nested values", () => {
    const cfg = balancedConfig();
    expect(getConfigValue(cfg, "risk.risk_per_trade_pct")).toBe(0.02);
    expect(getConfigValue(cfg, "signals.min_signal_score")).toBe(70);
    expect(getConfigValue(cfg, "execution.limit_chase.max_cross_pct")).toBe(0.002);
    expect(getConfigValue(cfg, "trading_enabled")).toBe(true);
  });

  it("getConfigValue should return undefined for bad paths", () => {
    const cfg = balancedConfig();
    expect(getConfigValue(cfg, "nonexistent.path")).toBeUndefined();
  });

  it("setConfigValue should return new config with updated value", () => {
    const cfg = balancedConfig();
    const updated = setConfigValue(cfg, "risk.risk_per_trade_pct", 0.03);
    // Original should be unchanged (immutable)
    expect(cfg.risk.risk_per_trade_pct).toBe(0.02);
    expect(updated.risk.risk_per_trade_pct).toBe(0.03);
  });

  it("setConfigValue should handle deeply nested paths", () => {
    const cfg = balancedConfig();
    const updated = setConfigValue(cfg, "execution.limit_chase.steps", 5);
    expect(updated.execution.limit_chase.steps).toBe(5);
    expect(cfg.execution.limit_chase.steps).toBe(3); // original unchanged
  });
});

// ─── Preset Tests ───────────────────────────────────────────────────────

describe("preset profiles", () => {
  it("should have conservative, balanced, and aggressive presets", () => {
    expect(PRESET_PROFILES).toHaveProperty("conservative");
    expect(PRESET_PROFILES).toHaveProperty("balanced");
    expect(PRESET_PROFILES).toHaveProperty("aggressive");
  });

  it("conservative should have lower risk than aggressive", () => {
    const cons = PRESET_PROFILES.conservative.config;
    const aggr = PRESET_PROFILES.aggressive.config;
    expect(cons.risk.risk_per_trade_pct).toBeLessThan(aggr.risk.risk_per_trade_pct);
    expect(cons.risk.max_notional_exposure_pct).toBeLessThan(aggr.risk.max_notional_exposure_pct);
  });

  it("conservative should have higher signal threshold than aggressive", () => {
    const cons = PRESET_PROFILES.conservative.config;
    const aggr = PRESET_PROFILES.aggressive.config;
    expect(cons.signals.min_signal_score).toBeGreaterThan(aggr.signals.min_signal_score);
  });

  it("balanced should have values between conservative and aggressive", () => {
    const cons = PRESET_PROFILES.conservative.config;
    const bal = PRESET_PROFILES.balanced.config;
    const aggr = PRESET_PROFILES.aggressive.config;
    expect(bal.risk.risk_per_trade_pct).toBeGreaterThan(cons.risk.risk_per_trade_pct);
    expect(bal.risk.risk_per_trade_pct).toBeLessThan(aggr.risk.risk_per_trade_pct);
  });
});
