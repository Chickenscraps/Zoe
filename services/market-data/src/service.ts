/**
 * MarketDataService — Polygon.io REST integration with caching + normalization.
 * Primary source for all market data in V4.
 */
import { createLogger } from "../../shared/src/logger.js";
import { getDb } from "../../shared/src/db.js";
import type { Quote, OHLCV, OptionContract, OptionChainSnapshot } from "../../shared/src/types.js";
import { TTLCache } from "./cache.js";
import {
  normalizeQuote,
  normalizeOHLCV,
  normalizeOptionContract,
  type PolygonLastTrade,
  type PolygonLastQuote,
  type PolygonAgg,
  type PolygonOptionSnapshot,
} from "./normalize.js";

const log = createLogger("market-data");

/** Polygon REST base URL */
const POLYGON_BASE = "https://api.polygon.io";

export interface MarketDataConfig {
  apiKey: string;
  quoteCacheTtl?: number;      // seconds, default 10
  historyCacheTtl?: number;    // seconds, default 300
  optionChainCacheTtl?: number; // seconds, default 60
  maxRequestsPerMin?: number;  // rate limit, default 5 (free tier)
}

export class MarketDataService {
  private apiKey: string;
  private quoteCache: TTLCache<Quote>;
  private historyCache: TTLCache<OHLCV[]>;
  private optionCache: TTLCache<OptionContract[]>;
  private requestCount = 0;
  private requestWindowStart = Date.now();
  private maxRequestsPerMin: number;

  constructor(config: MarketDataConfig) {
    this.apiKey = config.apiKey;
    this.quoteCache = new TTLCache(config.quoteCacheTtl ?? 10, 0);
    this.historyCache = new TTLCache(config.historyCacheTtl ?? 300, 0);
    this.optionCache = new TTLCache(config.optionChainCacheTtl ?? 60, 0);
    this.maxRequestsPerMin = config.maxRequestsPerMin ?? 5;
    log.info("MarketDataService initialized");
  }

  // ─── Rate Limiting ──────────────────────────────────────────────────

  private async checkRateLimit(): Promise<void> {
    const now = Date.now();
    const elapsed = now - this.requestWindowStart;

    if (elapsed > 60_000) {
      this.requestCount = 0;
      this.requestWindowStart = now;
    }

    if (this.requestCount >= this.maxRequestsPerMin) {
      const waitMs = 60_000 - elapsed + 100;
      log.warn("Rate limit approaching, waiting", { waitMs, count: this.requestCount });
      await new Promise((r) => setTimeout(r, waitMs));
      this.requestCount = 0;
      this.requestWindowStart = Date.now();
    }

    this.requestCount++;
  }

  // ─── HTTP Helper ────────────────────────────────────────────────────

  private async polygonGet<T>(path: string): Promise<T | null> {
    await this.checkRateLimit();

    const sep = path.includes("?") ? "&" : "?";
    const url = `${POLYGON_BASE}${path}${sep}apiKey=${this.apiKey}`;

    try {
      const res = await fetch(url);
      if (!res.ok) {
        log.error("Polygon API error", { path, status: res.status });
        return null;
      }
      return (await res.json()) as T;
    } catch (e) {
      log.error("Polygon fetch failed", { path, error: String(e) });
      return null;
    }
  }

  // ─── Quotes ─────────────────────────────────────────────────────────

  async getQuote(symbol: string): Promise<Quote | null> {
    const cached = this.quoteCache.get(symbol);
    if (cached) return cached;

    const [tradeRes, quoteRes] = await Promise.all([
      this.polygonGet<{ results?: PolygonLastTrade }>(`/v2/last/trade/${symbol}`),
      this.polygonGet<{ results?: PolygonLastQuote }>(`/v2/last/nbbo/${symbol}`),
    ]);

    const trade = tradeRes?.results ?? null;
    const nbbo = quoteRes?.results ?? null;

    if (!trade && !nbbo) {
      log.warn("No quote data available", { symbol });
      return null;
    }

    const quote = normalizeQuote(symbol, trade, nbbo);
    this.quoteCache.set(symbol, quote);
    return quote;
  }

  // ─── Historical Bars ────────────────────────────────────────────────

  async getHistory(
    symbol: string,
    days: number = 100,
    timespan: "minute" | "hour" | "day" | "week" = "day",
    multiplier: number = 1
  ): Promise<OHLCV[]> {
    const cacheKey = `${symbol}:${timespan}:${multiplier}:${days}`;
    const cached = this.historyCache.get(cacheKey);
    if (cached) return cached;

    const to = new Date();
    const from = new Date();
    from.setDate(from.getDate() - days);

    const fromStr = from.toISOString().split("T")[0];
    const toStr = to.toISOString().split("T")[0];

    const res = await this.polygonGet<{ results?: PolygonAgg[] }>(
      `/v2/aggs/ticker/${symbol}/range/${multiplier}/${timespan}/${fromStr}/${toStr}?adjusted=true&sort=asc&limit=5000`
    );

    if (!res?.results?.length) {
      log.warn("No history data", { symbol, timespan, days });
      return [];
    }

    const bars = res.results.map(normalizeOHLCV);
    this.historyCache.set(cacheKey, bars);
    return bars;
  }

  // ─── Option Chain ───────────────────────────────────────────────────

  async getOptionChain(
    underlying: string,
    opts?: { limit?: number; expiryDaysMax?: number }
  ): Promise<OptionContract[]> {
    const cached = this.optionCache.get(underlying);
    if (cached) return cached;

    const limit = opts?.limit ?? 250;

    const res = await this.polygonGet<{ results?: PolygonOptionSnapshot[] }>(
      `/v3/snapshot/options/${underlying}?limit=${limit}`
    );

    if (!res?.results?.length) {
      log.warn("No option chain data", { underlying });
      return [];
    }

    let contracts = res.results.map(normalizeOptionContract);

    if (opts?.expiryDaysMax) {
      const maxDate = new Date();
      maxDate.setDate(maxDate.getDate() + opts.expiryDaysMax);
      const maxStr = maxDate.toISOString().split("T")[0]!;
      contracts = contracts.filter((c) => c.expiry <= maxStr);
    }

    this.optionCache.set(underlying, contracts);
    return contracts;
  }

  /**
   * Fetch option chain and store snapshot to Supabase.
   */
  async snapshotOptionChain(underlying: string): Promise<OptionChainSnapshot | null> {
    const contracts = await this.getOptionChain(underlying);
    if (!contracts.length) return null;

    const snapshot: Omit<OptionChainSnapshot, "id"> = {
      underlying,
      snapshot_time: new Date().toISOString(),
      contracts,
    };

    try {
      const db = getDb();
      const { data, error } = await db
        .from("option_chain_snapshots")
        .insert({
          underlying,
          snapshot_time: snapshot.snapshot_time,
          contracts: JSON.stringify(contracts),
          contract_count: contracts.length,
        })
        .select("id")
        .single();

      if (error) {
        log.error("Failed to store option chain snapshot", { error: error.message });
        return null;
      }

      log.info("Option chain snapshot stored", {
        underlying,
        contracts: contracts.length,
        id: data.id,
      });

      return { ...snapshot, id: data.id } as OptionChainSnapshot;
    } catch (e) {
      log.error("Snapshot storage failed", { error: String(e) });
      return null;
    }
  }

  // ─── Cleanup ────────────────────────────────────────────────────────

  destroy(): void {
    this.quoteCache.destroy();
    this.historyCache.destroy();
    this.optionCache.destroy();
  }
}
