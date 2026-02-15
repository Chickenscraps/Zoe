/**
 * Heat Consensus Scoring — deterministic, explainable scoring for scanner cards.
 *
 * Produces a 0-100 score + tier (GOLD / WARM / COOL / COLD / BLOCKED)
 * from the existing candidate_scans data (score_breakdown + info).
 *
 * Supports BOTH old and new scanner data formats:
 *   Old breakdown: { liquidity, momentum, volatility, trend }
 *   New breakdown: { momentum, volume, spread, trend, mean_revert, mover, total, regime, edge_ratio, cost_usd }
 *   New info:      { mid, bid, ask, spread_pct, volume_24h, change_24h_pct, vwap, side, rsi, atr_pct, macd_hist, zscore, regime, indicators_valid }
 */

// ── Types ──────────────────────────────────────────────────────────────────

export type HeatTier = 'GOLD' | 'WARM' | 'COOL' | 'COLD' | 'BLOCKED';

export interface ScoreComponents {
  bounce_prob: number;
  trend_support_proximity: number;
  regime_ok: number;
  funding_ok: number;
  volatility_ok: number;
  liquidity_ok: number;
  hype_ok: number;
}

export interface HeatResult {
  symbol: string;
  score: number;
  tier: HeatTier;
  score_components: ScoreComponents;
  gates_failed: string[];
  reasons: string[];
}

// ── Config ─────────────────────────────────────────────────────────────────

const WEIGHTS = {
  bounce_prob: 0.30,
  trend_support_proximity: 0.20,
  regime_ok: 0.10,
  funding_ok: 0.10,
  volatility_ok: 0.10,
  liquidity_ok: 0.15,
  hype_ok: 0.05,
} as const;

const TIER_THRESHOLDS = {
  GOLD: 85,
  WARM: 70,
  COOL: 55,
} as const;

const GATE_LIMITS = {
  max_spread_pct: 0.50,
  max_vol_ann: 500,
  min_liquidity_score: 5,
  min_ticks: 4,
} as const;

// ── Helpers ────────────────────────────────────────────────────────────────

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

function norm(v: number, lo: number, hi: number): number {
  if (hi <= lo) return 0;
  return clamp((v - lo) / (hi - lo), 0, 1);
}

/** Detect if this is the new profit-maximizing scanner format */
function isNewFormat(breakdown: any): boolean {
  return breakdown.edge_ratio !== undefined || breakdown.mean_revert !== undefined || breakdown.volume !== undefined;
}

// ── Sub-score extractors (normalise raw info → 0..1) ───────────────────────

function extractBounceProb(info: any, breakdown: any): { value: number; reason: string } {
  // New format: use total score + edge ratio as primary signal
  if (isNewFormat(breakdown)) {
    const total = breakdown.total ?? 0;
    const edgeRatio = breakdown.edge_ratio ?? 0;
    const costPositive = edgeRatio >= 2.0;
    const scoreNorm = norm(total, 0, 100);
    const edgeNorm = clamp(edgeRatio / 5.0, 0, 1); // 5x edge = max
    const v = costPositive ? 0.5 * scoreNorm + 0.5 * edgeNorm : scoreNorm * 0.4;
    return {
      value: clamp(v, 0, 1),
      reason: `Score ${total.toFixed(0)}/100, edge ${edgeRatio.toFixed(1)}x${costPositive ? ' (cost-positive)' : ' (below threshold)'}`,
    };
  }

  // Old format: use consensus confidence if available
  const consensus = info.consensus;
  if (consensus) {
    const conf = clamp(consensus.confidence ?? 0, 0, 1);
    const gateRatio = consensus.gates_total > 0
      ? consensus.gates_passed / consensus.gates_total
      : 0;
    const v = 0.6 * conf + 0.4 * gateRatio;
    return {
      value: clamp(v, 0, 1),
      reason: `Consensus ${consensus.result} (${(conf * 100).toFixed(0)}% conf, ${consensus.gates_passed}/${consensus.gates_total} gates)`,
    };
  }
  // Fallback: use overall score normalised
  const overall = (breakdown.liquidity ?? 0) + (breakdown.momentum ?? 0)
    + (breakdown.volatility ?? 0) + (breakdown.trend ?? 0);
  const v = norm(overall, 0, 100);
  return { value: v, reason: `Overall score ${overall.toFixed(0)}/100` };
}

function extractTrendSupport(info: any, breakdown: any): { value: number; reason: string } {
  if (isNewFormat(breakdown)) {
    // New format: use trend score (0-20) + regime from breakdown
    const trendScore = norm(breakdown.trend ?? 0, 0, 20);
    const regime = info.regime ?? breakdown.regime ?? 'unknown';
    const regimeBoost = (regime === 'trending_up' || regime === 'trending_down') ? 0.3 : 0;
    const momentumNorm = norm(breakdown.momentum ?? 0, 0, 25);
    const v = 0.45 * trendScore + 0.30 * momentumNorm + 0.25 * regimeBoost;
    const reasons: string[] = [];
    if (trendScore > 0.5) reasons.push('strong trend');
    if (regime === 'trending_up') reasons.push('trending up');
    if (regime === 'trending_down') reasons.push('trending down');
    if (regime === 'mean_reverting') reasons.push('mean reverting');
    return {
      value: clamp(v + regimeBoost, 0, 1),
      reason: reasons.length > 0 ? reasons.join(', ') : 'trend unclear',
    };
  }

  // Old format
  const trendScore = norm(breakdown.trend ?? 0, 0, 25);
  const mtf = info.mtf_alignment != null ? clamp((info.mtf_alignment + 1) / 2, 0, 1) : 0.5;
  const ema = info.ema_crossover != null ? (info.ema_crossover > 0 ? 0.7 + norm(info.ema_crossover, 0, 0.5) * 0.3 : norm(info.ema_crossover, -0.5, 0) * 0.5) : 0.5;
  const v = 0.45 * trendScore + 0.35 * mtf + 0.20 * ema;
  const reasons: string[] = [];
  if (trendScore > 0.6) reasons.push('strong trend');
  if (mtf > 0.65) reasons.push('MTF aligned bullish');
  if (info.ema_crossover > 0) reasons.push('EMA bullish crossover');
  return {
    value: clamp(v, 0, 1),
    reason: reasons.length > 0 ? reasons.join(', ') : 'trend neutral',
  };
}

function extractRegime(info: any, breakdown?: any): { value: number; reason: string } {
  // New format: regime comes as a string directly in info or breakdown
  const regimeStr = info.regime ?? breakdown?.regime;
  if (typeof regimeStr === 'string') {
    if (regimeStr === 'trending_up') return { value: 0.9, reason: 'trending up regime' };
    if (regimeStr === 'trending_down') return { value: 0.6, reason: 'trending down regime' };
    if (regimeStr === 'mean_reverting') return { value: 0.5, reason: 'mean reverting regime' };
    if (regimeStr === 'choppy') return { value: 0.15, reason: 'choppy regime (avoid)' };
    if (regimeStr === 'unknown') return { value: 0.3, reason: 'regime unknown (warming)' };
  }

  // Old format: regime is an object { regime, confidence }
  const regime = info.regime;
  if (regime && typeof regime === 'object') {
    const r = regime.regime;
    const conf = clamp(regime.confidence ?? 0.5, 0, 1);
    if (r === 'bull') return { value: 0.7 + 0.3 * conf, reason: `bull regime (${(conf * 100).toFixed(0)}%)` };
    if (r === 'sideways') return { value: 0.4 + 0.2 * conf, reason: `sideways regime` };
    if (r === 'bear') return { value: 0.15 + 0.15 * conf, reason: `bear regime` };
    if (r === 'high_vol') return { value: 0.2, reason: 'high volatility regime' };
    return { value: 0.5, reason: `${r} regime` };
  }

  return { value: 0.5, reason: 'no regime data' };
}

function extractFunding(info: any, breakdown?: any): { value: number; reason: string } {
  // New format: use MACD histogram and RSI as funding proxy
  if (isNewFormat(breakdown ?? {})) {
    const macdHist = info.macd_hist ?? 0;
    const rsi = info.rsi ?? 50;
    const side = info.side;
    if (side === 'buy' && macdHist > 0) {
      return { value: 0.75 + norm(rsi, 30, 50) * 0.25, reason: `buy signal, MACD+ RSI=${rsi.toFixed(0)}` };
    }
    if (side === 'sell' && macdHist < 0) {
      return { value: 0.65, reason: `sell signal, MACD- RSI=${rsi.toFixed(0)}` };
    }
    if (macdHist > 0) return { value: 0.6, reason: 'MACD positive' };
    if (macdHist < 0) return { value: 0.35, reason: 'MACD negative' };
    return { value: 0.5, reason: 'momentum mixed' };
  }

  // Old format
  const momShort = info.momentum_short ?? 0;
  const momMed = info.momentum_medium ?? 0;
  const bullish = momShort > 0 && momMed > 0;
  const bearish = momShort < 0 && momMed < 0;
  if (bullish) {
    const v = 0.6 + norm(momShort + momMed, 0, 1) * 0.4;
    return { value: clamp(v, 0, 1), reason: `momentum bullish (+${momShort.toFixed(3)}%)` };
  }
  if (bearish) return { value: 0.25, reason: 'momentum bearish' };
  return { value: 0.5, reason: 'momentum mixed' };
}

function extractVolatility(info: any, breakdown: any): { value: number; reason: string } {
  if (isNewFormat(breakdown)) {
    // New format: use ATR% as volatility measure, BB squeeze from info
    const atrPct = info.atr_pct ?? 0;
    const bbSqueeze = info.bb_squeeze ?? false;
    let volEnv = 0.5;
    if (atrPct > 0) {
      if (atrPct < 0.1) volEnv = 0.95;       // Very low vol
      else if (atrPct < 0.3) volEnv = 0.8;    // Low vol
      else if (atrPct < 0.8) volEnv = 0.65;   // Moderate
      else if (atrPct < 1.5) volEnv = 0.45;   // Elevated
      else volEnv = 0.2;                        // High vol
    }
    const squeezeBonus = bbSqueeze ? 0.15 : 0;
    const v = volEnv + squeezeBonus;
    const reasons: string[] = [];
    if (atrPct > 0) reasons.push(`ATR ${atrPct.toFixed(2)}%`);
    if (bbSqueeze) reasons.push('BB squeeze (breakout pending)');
    if (atrPct > 1.0) reasons.push('elevated volatility');
    return {
      value: clamp(v, 0, 1),
      reason: reasons.length > 0 ? reasons.join(', ') : 'vol normal',
    };
  }

  // Old format
  const volScore = norm(breakdown.volatility ?? 0, 0, 20);
  const volAnn = info.volatility_ann;
  const boll = info.bollinger;
  let squeeze = false;
  if (boll?.squeeze) squeeze = true;
  let volEnv = 0.5;
  if (volAnn != null) {
    if (volAnn < 50) volEnv = 0.9;
    else if (volAnn < 100) volEnv = 0.7;
    else if (volAnn < 200) volEnv = 0.5;
    else if (volAnn < 350) volEnv = 0.3;
    else volEnv = 0.1;
  }
  const v = 0.5 * volScore + 0.35 * volEnv + (squeeze ? 0.15 : 0);
  const reasons: string[] = [];
  if (volAnn != null && volAnn < 100) reasons.push('low vol environment');
  if (squeeze) reasons.push('BB squeeze (breakout pending)');
  if (volAnn != null && volAnn > 200) reasons.push(`high vol (${volAnn.toFixed(0)}% ann)`);
  return {
    value: clamp(v, 0, 1),
    reason: reasons.length > 0 ? reasons.join(', ') : 'vol normal',
  };
}

function extractLiquidity(info: any, breakdown: any): { value: number; reason: string } {
  if (isNewFormat(breakdown)) {
    // New format: use spread score (0-15) + volume score (0-15)
    const spreadScore = norm(breakdown.spread ?? 0, 0, 15);
    const volumeScore = norm(breakdown.volume ?? 0, 0, 15);
    const spread = info.spread_pct;
    const volume = info.volume_24h;
    const v = 0.50 * spreadScore + 0.50 * volumeScore;
    const parts: string[] = [];
    if (spread != null) parts.push(`spread ${spread.toFixed(3)}%`);
    if (volume != null) parts.push(`vol $${(volume / 1000).toFixed(0)}K`);
    return {
      value: clamp(v, 0, 1),
      reason: parts.length > 0 ? parts.join(', ') : 'liquidity unknown',
    };
  }

  // Old format
  const liqScore = norm(breakdown.liquidity ?? 0, 0, 25);
  const spread = info.spread_pct;
  let spreadScore = 0.5;
  if (spread != null) {
    if (spread < 0.05) spreadScore = 1.0;
    else if (spread < 0.10) spreadScore = 0.85;
    else if (spread < 0.20) spreadScore = 0.65;
    else if (spread < 0.35) spreadScore = 0.4;
    else spreadScore = 0.15;
  }
  const v = 0.55 * liqScore + 0.45 * spreadScore;
  const reason = spread != null
    ? `spread ${spread.toFixed(3)}%, liq score ${(breakdown.liquidity ?? 0).toFixed(0)}/25`
    : `liq score ${(breakdown.liquidity ?? 0).toFixed(0)}/25`;
  return { value: clamp(v, 0, 1), reason };
}

function extractHype(info: any, breakdown: any): { value: number; reason: string } {
  if (isNewFormat(breakdown)) {
    // New format: use mover bonus + mean revert score as "interest" proxy
    const moverScore = norm(breakdown.mover ?? 0, 0, 10);
    const meanRevert = norm(breakdown.mean_revert ?? 0, 0, 15);
    const v = 0.6 * moverScore + 0.4 * meanRevert;
    const parts: string[] = [];
    if ((breakdown.mover ?? 0) > 0) parts.push(`mover bonus ${(breakdown.mover ?? 0).toFixed(0)}/10`);
    if ((breakdown.mean_revert ?? 0) > 0) parts.push(`mean revert ${(breakdown.mean_revert ?? 0).toFixed(0)}/15`);
    return {
      value: clamp(v, 0, 1),
      reason: parts.length > 0 ? parts.join(', ') : 'no special signals',
    };
  }

  // Old format
  const patterns = info.patterns ?? [];
  const bullishPatterns = patterns.filter((p: any) => p.direction === 'bullish').length;
  const momScore = norm(breakdown.momentum ?? 0, 0, 30);
  const patternBoost = clamp(bullishPatterns * 0.2, 0, 0.4);
  const v = 0.6 * momScore + 0.4 * patternBoost;
  const reason = bullishPatterns > 0
    ? `${bullishPatterns} bullish pattern(s), momentum ${(momScore * 100).toFixed(0)}%`
    : `momentum ${(momScore * 100).toFixed(0)}%`;
  return { value: clamp(v, 0, 1), reason };
}

// ── Gate checks ────────────────────────────────────────────────────────────

function applyGates(info: any, breakdown: any): string[] {
  const failed: string[] = [];

  const spread = info.spread_pct;
  if (spread != null && spread > GATE_LIMITS.max_spread_pct) {
    failed.push(`spread too wide (${spread.toFixed(3)}% > ${GATE_LIMITS.max_spread_pct}%)`);
  }

  if (isNewFormat(breakdown)) {
    // New format gates: regime check, cost check, indicator validity
    const regime = info.regime ?? breakdown.regime;
    if (regime === 'choppy') {
      failed.push('choppy regime (unreliable signals)');
    }
    if (!info.indicators_valid && info.indicators_valid !== undefined) {
      failed.push('indicators still warming up');
    }
    const edgeRatio = breakdown.edge_ratio ?? 0;
    if (edgeRatio > 0 && edgeRatio < 1.0) {
      failed.push(`edge too low (${edgeRatio.toFixed(1)}x < 1.0x cost)`);
    }
  } else {
    // Old format gates
    const volAnn = info.volatility_ann;
    if (volAnn != null && volAnn > GATE_LIMITS.max_vol_ann) {
      failed.push(`vol too high (${volAnn.toFixed(0)}% ann > ${GATE_LIMITS.max_vol_ann}%)`);
    }

    const liqScore = breakdown.liquidity ?? 0;
    if (liqScore < GATE_LIMITS.min_liquidity_score) {
      failed.push(`liquidity below threshold (${liqScore.toFixed(0)} < ${GATE_LIMITS.min_liquidity_score})`);
    }

    const ticks = info.tick_count ?? 0;
    if (ticks < GATE_LIMITS.min_ticks) {
      failed.push(`data stale (${ticks} ticks < ${GATE_LIMITS.min_ticks} required)`);
    }

    // Consensus engine blocking
    const consensus = info.consensus;
    if (consensus?.result === 'blocked') {
      const blockReasons = consensus.blocking_reasons ?? [];
      if (blockReasons.length > 0) {
        failed.push(...blockReasons.map((r: string) => `consensus: ${r}`));
      } else {
        failed.push('consensus engine blocked');
      }
    }
  }

  return failed;
}

// ── Main scoring function ──────────────────────────────────────────────────

export function computeHeatScore(
  symbol: string,
  info: any,
  breakdown: any,
): HeatResult {
  const gates_failed = applyGates(info, breakdown);

  // Extract each component
  const bounce = extractBounceProb(info, breakdown);
  const trend = extractTrendSupport(info, breakdown);
  const regime = extractRegime(info, breakdown);
  const funding = extractFunding(info, breakdown);
  const volatility = extractVolatility(info, breakdown);
  const liquidity = extractLiquidity(info, breakdown);
  const hype = extractHype(info, breakdown);

  const components: ScoreComponents = {
    bounce_prob: bounce.value,
    trend_support_proximity: trend.value,
    regime_ok: regime.value,
    funding_ok: funding.value,
    volatility_ok: volatility.value,
    liquidity_ok: liquidity.value,
    hype_ok: hype.value,
  };

  // Compute weighted score
  let raw = 0;
  for (const [key, weight] of Object.entries(WEIGHTS)) {
    raw += weight * components[key as keyof ScoreComponents];
  }

  const score = gates_failed.length > 0 ? 0 : Math.round(100 * clamp(raw, 0, 1));

  // Tier assignment
  let tier: HeatTier;
  if (gates_failed.length > 0) {
    tier = 'BLOCKED';
  } else if (score >= TIER_THRESHOLDS.GOLD) {
    tier = 'GOLD';
  } else if (score >= TIER_THRESHOLDS.WARM) {
    tier = 'WARM';
  } else if (score >= TIER_THRESHOLDS.COOL) {
    tier = 'COOL';
  } else {
    tier = 'COLD';
  }

  // Reasons
  const reasons: string[] = [];
  if (bounce.reason) reasons.push(bounce.reason);
  if (trend.reason) reasons.push(trend.reason);
  if (regime.reason) reasons.push(regime.reason);
  if (funding.reason) reasons.push(funding.reason);
  if (volatility.reason) reasons.push(volatility.reason);
  if (liquidity.reason) reasons.push(liquidity.reason);
  if (hype.reason) reasons.push(hype.reason);

  return { symbol, score, tier, score_components: components, gates_failed, reasons };
}

// ── Tier styling helpers ───────────────────────────────────────────────────

const GOLD_RGB = '212,175,55';

export function getTierAlpha(score: number, tier: HeatTier): number {
  if (tier === 'GOLD') return 0.22 + 0.18 * ((score - 85) / 15);
  if (tier === 'WARM') return 0.10 + 0.10 * ((score - 70) / 15);
  if (tier === 'COOL') return 0.04;
  return 0;
}

export interface TierStyle {
  background: string;
  border: string;
  boxShadow: string;
  badgeClass: string;
  badgeLabel: string;
  opacity: number;
}

export function getTierStyle(score: number, tier: HeatTier): TierStyle {
  const alpha = getTierAlpha(score, tier);

  if (tier === 'BLOCKED') {
    return {
      background: 'none',
      border: '1px solid rgba(239,68,68,0.25)',
      boxShadow: 'none',
      badgeClass: 'bg-red-500/15 text-red-400 border-red-500/25',
      badgeLabel: 'BLOCKED',
      opacity: 0.70,
    };
  }

  if (tier === 'GOLD') {
    return {
      background: `linear-gradient(100deg, rgba(${GOLD_RGB},${alpha.toFixed(3)}) 0%, rgba(${GOLD_RGB},${(alpha * 0.55).toFixed(3)}) 60%, transparent 100%)`,
      border: `1px solid rgba(${GOLD_RGB},${(alpha * 1.2).toFixed(3)})`,
      boxShadow: `0 0 0 1px rgba(${GOLD_RGB},${(alpha * 0.9).toFixed(3)}), 0 8px 24px rgba(0,0,0,0.35)`,
      badgeClass: 'bg-amber-500/20 text-amber-300 border-amber-400/30',
      badgeLabel: 'GOLD',
      opacity: 1,
    };
  }

  if (tier === 'WARM') {
    return {
      background: `linear-gradient(100deg, rgba(${GOLD_RGB},${alpha.toFixed(3)}) 0%, rgba(${GOLD_RGB},${(alpha * 0.55).toFixed(3)}) 60%, transparent 100%)`,
      border: `1px solid rgba(${GOLD_RGB},${(alpha * 1.2).toFixed(3)})`,
      boxShadow: `0 4px 16px rgba(0,0,0,0.3)`,
      badgeClass: 'bg-amber-500/10 text-amber-400/80 border-amber-500/20',
      badgeLabel: 'WARM',
      opacity: 1,
    };
  }

  if (tier === 'COOL') {
    return {
      background: 'none',
      border: `1px solid rgba(${GOLD_RGB},0.08)`,
      boxShadow: 'none',
      badgeClass: 'bg-white/5 text-text-muted border-white/10',
      badgeLabel: 'COOL',
      opacity: 1,
    };
  }

  // COLD
  return {
    background: 'none',
    border: '1px solid rgba(255,255,255,0.06)',
    boxShadow: 'none',
    badgeClass: 'bg-white/5 text-text-dim border-white/8',
    badgeLabel: 'COLD',
    opacity: 1,
  };
}

// ── Sort comparator ────────────────────────────────────────────────────────

const TIER_PRIORITY: Record<HeatTier, number> = {
  GOLD: 0,
  WARM: 1,
  COOL: 2,
  COLD: 3,
  BLOCKED: 4,
};

export function heatSort(a: HeatResult, b: HeatResult): number {
  const tierDiff = TIER_PRIORITY[a.tier] - TIER_PRIORITY[b.tier];
  if (tierDiff !== 0) return tierDiff;
  return b.score - a.score;
}

// ── Component label formatting ─────────────────────────────────────────────

export const COMPONENT_LABELS: Record<keyof ScoreComponents, { label: string; weight: number }> = {
  bounce_prob: { label: 'Edge / Score', weight: 30 },
  trend_support_proximity: { label: 'Trend/Support', weight: 20 },
  regime_ok: { label: 'Regime', weight: 10 },
  funding_ok: { label: 'Momentum', weight: 10 },
  volatility_ok: { label: 'Volatility', weight: 10 },
  liquidity_ok: { label: 'Liquidity', weight: 15 },
  hype_ok: { label: 'Signals', weight: 5 },
};
