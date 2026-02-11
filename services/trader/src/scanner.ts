/**
 * Scanner — Scans the market for trade candidates.
 * Runs during market hours. Filters down to a shortlist based on
 * strategy criteria, liquidity, and research signals.
 */
import { createLogger } from "../../shared/src/logger.js";
import type { OptionContract, Quote, FeatureDaily } from "../../shared/src/types.js";

const log = createLogger("trader:scanner");

export interface ScanFilter {
  minVolume: number;
  minOpenInterest: number;
  maxDaysToExpiry: number;
  minIV: number;
  maxIV: number;
  minDelta: number;
  maxDelta: number;
}

const DEFAULT_FILTER: ScanFilter = {
  minVolume: 100,
  minOpenInterest: 500,
  maxDaysToExpiry: 45,
  minIV: 0.15,
  maxIV: 0.80,
  minDelta: 0.15,
  maxDelta: 0.50,
};

export interface ScanCandidate {
  contract: OptionContract;
  score: number;
  reasons: string[];
}

/**
 * Filter an option chain down to tradeable candidates.
 */
export function scanOptionChain(
  contracts: OptionContract[],
  filter: Partial<ScanFilter> = {}
): ScanCandidate[] {
  const f = { ...DEFAULT_FILTER, ...filter };
  const now = new Date();
  const candidates: ScanCandidate[] = [];

  for (const c of contracts) {
    const reasons: string[] = [];
    let score = 0;

    // Liquidity check
    if (c.volume < f.minVolume) continue;
    if (c.open_interest < f.minOpenInterest) continue;

    // Expiry check
    const expiry = new Date(c.expiry);
    const daysToExpiry = Math.ceil((expiry.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    if (daysToExpiry <= 0 || daysToExpiry > f.maxDaysToExpiry) continue;

    // IV check
    if (c.implied_volatility < f.minIV || c.implied_volatility > f.maxIV) continue;

    // Delta check
    const absDelta = Math.abs(c.greeks.delta ?? 0);
    if (absDelta < f.minDelta || absDelta > f.maxDelta) continue;

    // Score: higher volume + tighter spread = better
    const spread = c.ask - c.bid;
    const spreadPct = c.mid > 0 ? spread / c.mid : 1;
    score += Math.min(c.volume / 1000, 5);          // up to 5 pts for volume
    score += Math.min(c.open_interest / 5000, 3);   // up to 3 pts for OI
    score += Math.max(0, (1 - spreadPct) * 3);      // up to 3 pts for tight spread
    score += c.implied_volatility * 2;               // IV bonus

    if (spreadPct < 0.05) reasons.push("tight spread");
    if (c.volume > 1000) reasons.push("high volume");
    if (c.open_interest > 5000) reasons.push("deep OI");
    if (daysToExpiry <= 14) reasons.push("near-term");

    candidates.push({ contract: c, score, reasons });
  }

  // Sort by score descending
  candidates.sort((a, b) => b.score - a.score);

  log.info("Scan complete", {
    total: contracts.length,
    passed: candidates.length,
  });

  return candidates;
}

/**
 * Rank candidates using research features if available.
 */
export function rankWithResearch(
  candidates: ScanCandidate[],
  features: FeatureDaily[]
): ScanCandidate[] {
  const featureMap = new Map(features.map((f) => [f.symbol, f]));

  for (const c of candidates) {
    const underlying = c.contract.underlying;
    const feat = featureMap.get(underlying);
    if (feat) {
      // Boost score based on research signals
      const sentiment = (feat.features["sentiment"] ?? 0);
      const momentum = (feat.features["momentum"] ?? 0);
      c.score += sentiment * 2;
      c.score += momentum * 1.5;
      if (sentiment > 0.5) c.reasons.push("bullish sentiment");
      if (momentum > 0.5) c.reasons.push("positive momentum");
    }
  }

  candidates.sort((a, b) => b.score - a.score);
  return candidates;
}
