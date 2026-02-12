/**
 * Zoe V4 — ConfigLoader
 *
 * Bot-side service that loads the active strategy config from Supabase,
 * polls for changes, and applies them atomically (hot-reload).
 *
 * Usage:
 *   const loader = new ConfigLoader("paper");
 *   await loader.start();
 *   const cfg = loader.config;  // always the latest valid config
 *   // ... on trade intent:
 *   const { version, checksum } = loader.metadata;
 */
import type { SupabaseClient } from "@supabase/supabase-js";
import { getDb } from "./db.js";
import { createLogger } from "./logger.js";
import {
  validateConfig,
  configChecksum,
  type StrategyConfig,
  PRESET_PROFILES,
} from "./strategy-config.js";

const log = createLogger("config-loader");

export interface ConfigMetadata {
  version: number;
  checksum: string;
  name: string;
  loadedAt: Date;
}

export class ConfigLoader {
  private _config: StrategyConfig;
  private _metadata: ConfigMetadata;
  private _mode: "paper" | "live";
  private _db: SupabaseClient;
  private _pollInterval: ReturnType<typeof setInterval> | null = null;
  private _realtimeChannel: ReturnType<SupabaseClient["channel"]> | null = null;
  private _listeners: Array<(config: StrategyConfig, meta: ConfigMetadata) => void> = [];

  constructor(mode: "paper" | "live", db?: SupabaseClient) {
    this._mode = mode;
    this._db = db ?? getDb();
    // Start with balanced preset as fallback
    this._config = PRESET_PROFILES.balanced.config;
    this._metadata = {
      version: 0,
      checksum: "fallback",
      name: "balanced (fallback)",
      loadedAt: new Date(),
    };
  }

  /** Current active config (always valid). */
  get config(): StrategyConfig {
    return this._config;
  }

  /** Metadata about the current config (version, checksum). */
  get metadata(): ConfigMetadata {
    return this._metadata;
  }

  /** Register a listener for config changes. */
  onChange(fn: (config: StrategyConfig, meta: ConfigMetadata) => void): () => void {
    this._listeners.push(fn);
    return () => {
      this._listeners = this._listeners.filter((l) => l !== fn);
    };
  }

  /**
   * Load the active config from DB. If none exists or invalid,
   * keep the last known good config.
   */
  async load(): Promise<boolean> {
    try {
      const { data, error } = await this._db
        .from("strategy_configs")
        .select("*")
        .eq("mode", this._mode)
        .eq("is_active", true)
        .limit(1)
        .maybeSingle();

      if (error) {
        log.error("Config fetch error", { error: error.message });
        return false;
      }

      if (!data) {
        log.warn("No active config found for mode", { mode: this._mode });
        return false;
      }

      // Skip if same version already loaded
      if (data.version === this._metadata.version && data.checksum === this._metadata.checksum) {
        return true;
      }

      // Validate the config
      let parsed: StrategyConfig;
      try {
        parsed = validateConfig(data.config_json);
      } catch (validationErr) {
        log.error("Config validation rejected — keeping last-good config", {
          version: data.version,
          error: String(validationErr),
        });
        // Log rejection event
        await this._db.from("audit_log").insert({
          actor: "config-loader",
          action: "config_rejected",
          severity: "warn",
          details: {
            mode: this._mode,
            version: data.version,
            reason: String(validationErr),
          },
          timestamp: new Date().toISOString(),
        }).then(() => {});
        return false;
      }

      // Verify checksum integrity
      const computed = configChecksum(parsed);
      if (computed !== data.checksum) {
        log.warn("Config checksum mismatch — applying anyway but logging", {
          expected: data.checksum,
          computed,
          version: data.version,
        });
      }

      // Apply atomically
      const prevVersion = this._metadata.version;
      this._config = parsed;
      this._metadata = {
        version: data.version,
        checksum: data.checksum,
        name: data.name,
        loadedAt: new Date(),
      };

      log.info("Config applied", {
        mode: this._mode,
        version: data.version,
        prevVersion,
        name: data.name,
      });

      // Notify listeners
      for (const listener of this._listeners) {
        try {
          listener(this._config, this._metadata);
        } catch (e) {
          log.error("Config change listener error", { error: String(e) });
        }
      }

      // Log applied event
      await this._db.from("audit_log").insert({
        actor: "config-loader",
        action: "config_applied",
        severity: "info",
        details: {
          mode: this._mode,
          version: data.version,
          name: data.name,
          checksum: data.checksum,
        },
        timestamp: new Date().toISOString(),
      }).then(() => {});

      return true;
    } catch (e) {
      log.error("Config load failed", { error: String(e) });
      return false;
    }
  }

  /**
   * Start the config loader:
   * 1. Load initial config
   * 2. Subscribe to Supabase realtime changes
   * 3. Start polling as fallback (every 30s)
   */
  async start(pollIntervalMs = 30_000): Promise<void> {
    log.info("ConfigLoader starting", { mode: this._mode });

    // Initial load
    await this.load();

    // Subscribe to realtime changes
    try {
      this._realtimeChannel = this._db
        .channel(`config_changes_${this._mode}`)
        .on(
          "postgres_changes",
          {
            event: "*",
            schema: "public",
            table: "strategy_configs",
            filter: `mode=eq.${this._mode}`,
          },
          () => {
            log.info("Realtime config change detected, reloading...");
            this.load();
          }
        )
        .subscribe();
    } catch (e) {
      log.warn("Realtime subscription failed, relying on polling", { error: String(e) });
    }

    // Polling fallback
    this._pollInterval = setInterval(() => {
      this.load();
    }, pollIntervalMs);
  }

  /** Stop the config loader. */
  async stop(): Promise<void> {
    if (this._pollInterval) {
      clearInterval(this._pollInterval);
      this._pollInterval = null;
    }
    if (this._realtimeChannel) {
      await this._db.removeChannel(this._realtimeChannel);
      this._realtimeChannel = null;
    }
    this._listeners = [];
    log.info("ConfigLoader stopped", { mode: this._mode });
  }
}
