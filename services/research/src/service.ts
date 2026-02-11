/**
 * ResearchService — Off-hours research ingestion pipeline.
 * Fetches from multiple sources, stores to Supabase, and builds feature vectors.
 * Runs during off-hours only (controlled by jobs scheduler).
 */
import { createLogger } from "../../shared/src/logger.js";
import { getDb, auditLog } from "../../shared/src/db.js";
import type { ResearchItem, FeatureDaily, ResearchSource } from "../../shared/src/types.js";
import {
  fetchGoogleTrends,
  fetchXPosts,
  fetchBloomberg,
  type TrendsConfig,
  type XConfig,
  type BloombergConfig,
} from "./connectors.js";

const log = createLogger("research");

export interface ResearchConfig {
  trends: TrendsConfig;
  x: XConfig;
  bloomberg: BloombergConfig;
  symbols: string[];
}

const DEFAULT_CONFIG: ResearchConfig = {
  trends: {},
  x: {},
  bloomberg: {},
  symbols: ["SPY", "QQQ", "IWM", "AAPL", "TSLA"],
};

export class ResearchService {
  private config: ResearchConfig;

  constructor(config: Partial<ResearchConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    log.info("ResearchService initialized", { symbols: this.config.symbols.length });
  }

  /**
   * Run the full research pipeline for all configured symbols.
   */
  async runPipeline(): Promise<{
    itemsFetched: number;
    itemsStored: number;
    featuresBuilt: number;
  }> {
    log.info("Starting research pipeline", { symbols: this.config.symbols });

    const [trends, xPosts, bloomberg] = await Promise.all([
      fetchGoogleTrends(this.config.symbols, this.config.trends),
      fetchXPosts(this.config.symbols, this.config.x),
      fetchBloomberg(this.config.symbols, this.config.bloomberg),
    ]);

    const allItems = [...trends, ...xPosts, ...bloomberg];
    log.info("Research fetched", {
      trends: trends.length,
      x: xPosts.length,
      bloomberg: bloomberg.length,
      total: allItems.length,
    });

    const stored = await this.storeItems(allItems);
    const features = await this.buildDailyFeatures(allItems);

    await auditLog("research_pipeline_completed", {
      itemsFetched: allItems.length,
      itemsStored: stored,
      featuresBuilt: features,
    });

    return { itemsFetched: allItems.length, itemsStored: stored, featuresBuilt: features };
  }

  async fetchLatest(symbols?: string[]): Promise<ResearchItem[]> {
    const syms = symbols ?? this.config.symbols;
    const [trends, xPosts] = await Promise.all([
      fetchGoogleTrends(syms, this.config.trends),
      fetchXPosts(syms, this.config.x),
    ]);
    return [...trends, ...xPosts];
  }

  private async storeItems(items: ResearchItem[]): Promise<number> {
    if (items.length === 0) return 0;
    try {
      const db = getDb();
      const rows = items.map((item) => ({
        source: item.source,
        symbol: item.symbol,
        title: item.title,
        content: item.content,
        sentiment_score: item.sentiment_score,
        relevance_score: item.relevance_score,
        fetched_at: item.fetched_at,
        metadata: item.metadata,
      }));
      const { error } = await db.from("research_items").insert(rows);
      if (error) {
        log.error("Failed to store research items", { error: error.message });
        return 0;
      }
      log.info("Research items stored", { count: rows.length });
      return rows.length;
    } catch (e) {
      log.error("storeItems error", { error: String(e) });
      return 0;
    }
  }

  private async buildDailyFeatures(items: ResearchItem[]): Promise<number> {
    const today = new Date().toISOString().split("T")[0]!;
    const bySymbol = new Map<string, ResearchItem[]>();

    for (const item of items) {
      if (!item.symbol) continue;
      const existing = bySymbol.get(item.symbol) ?? [];
      existing.push(item);
      bySymbol.set(item.symbol, existing);
    }

    let built = 0;
    try {
      const db = getDb();
      for (const [symbol, symbolItems] of bySymbol) {
        const sentiments = symbolItems
          .map((i) => i.sentiment_score)
          .filter((s): s is number => s !== null);
        const avgSentiment = sentiments.length > 0
          ? sentiments.reduce((a, b) => a + b, 0) / sentiments.length
          : 0;

        const sourceCount: Record<string, number> = {};
        for (const item of symbolItems) {
          sourceCount[item.source] = (sourceCount[item.source] ?? 0) + 1;
        }

        const features: Record<string, number> = {
          sentiment: avgSentiment,
          mention_count: symbolItems.length,
          source_diversity: Object.keys(sourceCount).length,
          trends_count: sourceCount["google_trends"] ?? 0,
          x_count: sourceCount["x_twitter"] ?? 0,
          bloomberg_count: sourceCount["bloomberg"] ?? 0,
        };

        const { error } = await db
          .from("features_daily")
          .upsert({ symbol, date: today, features, source_ids: symbolItems.map((i) => i.id) }, { onConflict: "symbol,date" });

        if (!error) built++;
        else log.error("Failed to upsert features", { symbol, error: error.message });
      }
    } catch (e) {
      log.error("buildDailyFeatures error", { error: String(e) });
    }

    log.info("Daily features built", { count: built });
    return built;
  }

  async getFeatures(symbol: string, date?: string): Promise<FeatureDaily | null> {
    try {
      const db = getDb();
      const d = date ?? new Date().toISOString().split("T")[0]!;
      const { data, error } = await db
        .from("features_daily")
        .select("*")
        .eq("symbol", symbol)
        .eq("date", d)
        .single();
      if (error || !data) return null;
      return data as unknown as FeatureDaily;
    } catch {
      return null;
    }
  }
}
