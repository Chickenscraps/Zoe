/**
 * Research Connectors — Fetch data from external research sources.
 * Each connector is a standalone async function that returns ResearchItem[].
 * Bloomberg is stubbed with a legal-safe fallback.
 */
import { createLogger } from "../../shared/src/logger.js";
import type { ResearchItem, ResearchSource } from "../../shared/src/types.js";

const log = createLogger("research:connectors");

// ─── Google Trends Connector ────────────────────────────────────────

export interface TrendsConfig {
  apiKey?: string;
}

/**
 * Fetch trending data for given symbols from Google Trends.
 * If no API key, returns empty (graceful degradation).
 */
export async function fetchGoogleTrends(
  symbols: string[],
  config: TrendsConfig = {}
): Promise<ResearchItem[]> {
  if (!config.apiKey) {
    log.debug("Google Trends: no API key, skipping");
    return [];
  }

  const items: ResearchItem[] = [];

  try {
    // Google Trends API call (simplified — real impl would use serpapi or pytrends proxy)
    for (const symbol of symbols) {
      const url = `https://serpapi.com/search.json?engine=google_trends&q=${symbol}&api_key=${config.apiKey}`;

      try {
        const res = await fetch(url);
        if (!res.ok) continue;

        const data = await res.json() as Record<string, unknown>;
        items.push({
          id: crypto.randomUUID(),
          source: "google_trends" as ResearchSource,
          symbol,
          title: `Google Trends: ${symbol}`,
          content: JSON.stringify(data).slice(0, 500),
          sentiment_score: null,
          relevance_score: null,
          fetched_at: new Date().toISOString(),
          metadata: { raw_interest: data },
        });
      } catch {
        log.warn("Trends fetch failed for symbol", { symbol });
      }
    }
  } catch (e) {
    log.error("Google Trends connector error", { error: String(e) });
  }

  log.info("Google Trends fetched", { count: items.length, symbols: symbols.length });
  return items;
}

// ─── X/Twitter Connector ────────────────────────────────────────────

export interface XConfig {
  bearerToken?: string;
}

/**
 * Fetch recent posts about symbols from X/Twitter.
 */
export async function fetchXPosts(
  symbols: string[],
  config: XConfig = {}
): Promise<ResearchItem[]> {
  if (!config.bearerToken) {
    log.debug("X/Twitter: no bearer token, skipping");
    return [];
  }

  const items: ResearchItem[] = [];

  try {
    for (const symbol of symbols) {
      const query = encodeURIComponent(`$${symbol} OR #${symbol} lang:en -is:retweet`);
      const url = `https://api.twitter.com/2/tweets/search/recent?query=${query}&max_results=10&tweet.fields=created_at,public_metrics`;

      try {
        const res = await fetch(url, {
          headers: { Authorization: `Bearer ${config.bearerToken}` },
        });
        if (!res.ok) continue;

        const data = await res.json() as { data?: Array<{ id: string; text: string; created_at?: string; public_metrics?: Record<string, number> }> };
        for (const tweet of data.data ?? []) {
          items.push({
            id: crypto.randomUUID(),
            source: "x_twitter" as ResearchSource,
            symbol,
            title: `X: ${symbol}`,
            content: tweet.text?.slice(0, 280) ?? "",
            sentiment_score: null, // TODO: run sentiment analysis
            relevance_score: null,
            fetched_at: new Date().toISOString(),
            metadata: {
              tweet_id: tweet.id,
              created_at: tweet.created_at,
              metrics: tweet.public_metrics,
            },
          });
        }
      } catch {
        log.warn("X fetch failed for symbol", { symbol });
      }
    }
  } catch (e) {
    log.error("X/Twitter connector error", { error: String(e) });
  }

  log.info("X/Twitter fetched", { count: items.length, symbols: symbols.length });
  return items;
}

// ─── Bloomberg Connector (Stub) ─────────────────────────────────────

export interface BloombergConfig {
  apiKey?: string;
}

/**
 * Bloomberg connector — ONLY via licensed feed.
 * If no API key, returns a stub with legal-safe fallback message.
 */
export async function fetchBloomberg(
  symbols: string[],
  config: BloombergConfig = {}
): Promise<ResearchItem[]> {
  if (!config.apiKey) {
    log.info("Bloomberg: no API key (licensed feed required). Using stub.");
    return symbols.map((symbol) => ({
      id: crypto.randomUUID(),
      source: "bloomberg" as ResearchSource,
      symbol,
      title: `Bloomberg stub: ${symbol}`,
      content: "Bloomberg data requires a licensed API feed. Configure BLOOMBERG_API_KEY to enable.",
      sentiment_score: null,
      relevance_score: null,
      fetched_at: new Date().toISOString(),
      metadata: { stub: true },
    }));
  }

  // Real Bloomberg API integration would go here
  // This is intentionally minimal — actual Bloomberg Terminal/API
  // requires specific SDK and licensing terms.
  log.warn("Bloomberg API integration not yet implemented beyond stub");
  return [];
}
