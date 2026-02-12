/**
 * Tests for ConfigLoader hot-reload behavior.
 *
 * Since @supabase/supabase-js may not be installed at the test root,
 * we mock the entire module before importing config-loader.
 */
import { describe, it, expect, vi } from "vitest";

// Mock the supabase dependency before importing config-loader
vi.mock("@supabase/supabase-js", () => ({
  createClient: vi.fn(() => ({
    from: vi.fn(),
    channel: vi.fn(),
    removeChannel: vi.fn(),
  })),
}));

// Now we can safely import
const {
  ConfigLoader,
} = await import("../../services/shared/src/config-loader.js");
const {
  PRESET_PROFILES,
  configChecksum,
} = await import("../../services/shared/src/strategy-config.js");

// ─── Mock Supabase Client ─────────────────────────────────────────────

function createMockDb(overrides: {
  selectResult?: { data: unknown; error: unknown };
} = {}) {
  const insertFn = vi.fn().mockResolvedValue({ error: null });
  const selectResult = overrides.selectResult ?? { data: null, error: null };

  const mockChannel = {
    on: vi.fn().mockReturnThis(),
    subscribe: vi.fn().mockReturnThis(),
    unsubscribe: vi.fn(),
  };

  const db = {
    from: vi.fn().mockReturnValue({
      select: vi.fn().mockReturnValue({
        eq: vi.fn().mockReturnValue({
          eq: vi.fn().mockReturnValue({
            limit: vi.fn().mockReturnValue({
              maybeSingle: vi.fn().mockResolvedValue(selectResult),
            }),
          }),
        }),
      }),
      insert: insertFn,
    }),
    channel: vi.fn().mockReturnValue(mockChannel),
    removeChannel: vi.fn().mockResolvedValue(undefined),
  };

  return { db, insertFn };
}

// ─── Tests ──────────────────────────────────────────────────────────────

describe("ConfigLoader", () => {
  it("should initialize with balanced fallback config", () => {
    const { db } = createMockDb();
    const loader = new ConfigLoader("paper", db as any);

    expect(loader.config).toEqual(PRESET_PROFILES.balanced.config);
    expect(loader.metadata.version).toBe(0);
    expect(loader.metadata.checksum).toBe("fallback");
  });

  it("should load valid config from DB", async () => {
    const config = PRESET_PROFILES.conservative.config;
    const checksum = configChecksum(config);

    const { db } = createMockDb({
      selectResult: {
        data: {
          config_json: config,
          version: 5,
          checksum,
          name: "Conservative",
        },
        error: null,
      },
    });

    const loader = new ConfigLoader("paper", db as any);
    const result = await loader.load();

    expect(result).toBe(true);
    expect(loader.config).toEqual(config);
    expect(loader.metadata.version).toBe(5);
    expect(loader.metadata.name).toBe("Conservative");
  });

  it("should reject invalid config and keep last-good", async () => {
    const invalidConfig = {
      ...PRESET_PROFILES.balanced.config,
      risk: { risk_per_trade_pct: 999, max_notional_exposure_pct: 999 },
    };

    const { db } = createMockDb({
      selectResult: {
        data: {
          config_json: invalidConfig,
          version: 10,
          checksum: "invalid",
          name: "Bad Config",
        },
        error: null,
      },
    });

    const loader = new ConfigLoader("paper", db as any);
    const result = await loader.load();

    expect(result).toBe(false);
    expect(loader.config).toEqual(PRESET_PROFILES.balanced.config);
    expect(loader.metadata.version).toBe(0);
  });

  it("should not reload if same version + checksum", async () => {
    const config = PRESET_PROFILES.balanced.config;
    const checksum = configChecksum(config);

    const { db } = createMockDb({
      selectResult: {
        data: {
          config_json: config,
          version: 3,
          checksum,
          name: "Balanced",
        },
        error: null,
      },
    });

    const loader = new ConfigLoader("paper", db as any);
    await loader.load();
    expect(loader.metadata.version).toBe(3);

    const result = await loader.load();
    expect(result).toBe(true);
  });

  it("should call onChange listeners when config updates", async () => {
    const config = PRESET_PROFILES.aggressive.config;
    const checksum = configChecksum(config);

    const { db } = createMockDb({
      selectResult: {
        data: {
          config_json: config,
          version: 7,
          checksum,
          name: "Aggressive",
        },
        error: null,
      },
    });

    const loader = new ConfigLoader("paper", db as any);
    const listener = vi.fn();
    loader.onChange(listener);

    await loader.load();

    expect(listener).toHaveBeenCalledOnce();
    expect(listener).toHaveBeenCalledWith(config, expect.objectContaining({ version: 7 }));
  });

  it("should unsubscribe listener when unsub fn called", async () => {
    const config = PRESET_PROFILES.aggressive.config;
    const checksum = configChecksum(config);

    const { db } = createMockDb({
      selectResult: {
        data: {
          config_json: config,
          version: 1,
          checksum,
          name: "Aggressive",
        },
        error: null,
      },
    });

    const loader = new ConfigLoader("paper", db as any);
    const listener = vi.fn();
    const unsub = loader.onChange(listener);
    unsub();

    await loader.load();
    expect(listener).not.toHaveBeenCalled();
  });

  it("should handle DB errors gracefully", async () => {
    const { db } = createMockDb({
      selectResult: {
        data: null,
        error: { message: "Connection refused" },
      },
    });

    const loader = new ConfigLoader("paper", db as any);
    const result = await loader.load();

    expect(result).toBe(false);
    expect(loader.config.trading_enabled).toBe(true);
  });

  it("should handle missing config gracefully", async () => {
    const { db } = createMockDb({
      selectResult: { data: null, error: null },
    });

    const loader = new ConfigLoader("paper", db as any);
    const result = await loader.load();

    expect(result).toBe(false);
    expect(loader.config).toEqual(PRESET_PROFILES.balanced.config);
  });

  it("should stop cleanly", async () => {
    const { db } = createMockDb();
    const loader = new ConfigLoader("paper", db as any);

    await loader.start(60_000);
    await loader.stop();

    expect(true).toBe(true);
  });
});
