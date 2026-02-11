/**
 * Tests for @zoe/shared config validation
 */
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { loadConfig, paperBrokerConfigSchema } from "../../services/shared/src/config.js";

describe("@zoe/shared config", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  it("should throw on missing required SUPABASE_URL", () => {
    process.env["SUPABASE_KEY"] = "test-key";
    process.env["POLYGON_API_KEY"] = "test-polygon";
    process.env["DISCORD_TOKEN"] = "test-token";
    process.env["DISCORD_CHANNEL_ID"] = "123";
    // SUPABASE_URL intentionally missing

    expect(() => loadConfig()).toThrow("SUPABASE_URL");
  });

  it("should validate paper broker defaults", () => {
    process.env["SUPABASE_URL"] = "https://test.supabase.co";
    process.env["SUPABASE_KEY"] = "test-key";

    const config = loadConfig(paperBrokerConfigSchema);

    expect(config.PAPER_STARTING_EQUITY).toBe(2000);
    expect(config.PAPER_MAX_RISK_PER_TRADE).toBe(100);
    expect(config.PAPER_PDT_MAX_DAY_TRADES).toBe(3);
    expect(config.PAPER_PDT_WINDOW_DAYS).toBe(5);
    expect(config.PAPER_PESSIMISTIC_FILLS).toBe(true);
    expect(config.PAPER_SLIPPAGE_BPS).toBe(5);
  });

  it("should accept custom paper broker settings", () => {
    process.env["SUPABASE_URL"] = "https://test.supabase.co";
    process.env["SUPABASE_KEY"] = "test-key";
    process.env["PAPER_STARTING_EQUITY"] = "5000";
    process.env["PAPER_PESSIMISTIC_FILLS"] = "false";
    process.env["PAPER_SLIPPAGE_BPS"] = "10";

    const config = loadConfig(paperBrokerConfigSchema);

    expect(config.PAPER_STARTING_EQUITY).toBe(5000);
    expect(config.PAPER_PESSIMISTIC_FILLS).toBe(false);
    expect(config.PAPER_SLIPPAGE_BPS).toBe(10);
  });
});
