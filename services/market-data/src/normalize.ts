/**
 * Polygon data → Zoe normalized types
 * Clean transformations with null-safety.
 */
import type { Quote, OHLCV, OptionContract, Greeks } from "../../shared/src/types.js";

// ─── Polygon response shapes (partial, what we need) ─────────────────

export interface PolygonLastTrade {
  T?: string;   // ticker
  p?: number;   // price
  s?: number;   // size
  t?: number;   // timestamp (unix ns)
}

export interface PolygonLastQuote {
  T?: string;
  P?: number;   // ask
  p?: number;   // bid
  S?: number;   // ask size
  s?: number;   // bid size
  t?: number;
}

export interface PolygonAgg {
  T?: string;
  o?: number;
  h?: number;
  l?: number;
  c?: number;
  v?: number;
  t?: number;   // timestamp ms
}

export interface PolygonOptionSnapshot {
  details?: {
    ticker?: string;
    expiration_date?: string;
    strike_price?: number;
    contract_type?: string;
  };
  greeks?: {
    delta?: number;
    gamma?: number;
    theta?: number;
    vega?: number;
  };
  implied_volatility?: number;
  day?: {
    close?: number;
    volume?: number;
    open_interest?: number;
    last?: { price?: number };
  };
  last_quote?: {
    bid?: number;
    ask?: number;
    bid_size?: number;
    ask_size?: number;
  };
  underlying_asset?: {
    ticker?: string;
  };
}

// ─── Normalizers ─────────────────────────────────────────────────────

export function normalizeQuote(
  symbol: string,
  trade: PolygonLastTrade | null,
  quote: PolygonLastQuote | null
): Quote {
  const price = trade?.p ?? 0;
  const bid = quote?.p ?? 0;
  const ask = quote?.P ?? 0;
  const ts = trade?.t ? Math.floor(trade.t / 1_000_000) : Date.now(); // ns → ms

  return {
    symbol,
    price,
    bid,
    ask,
    timestamp: ts,
  };
}

export function normalizeOHLCV(agg: PolygonAgg): OHLCV {
  return {
    timestamp: agg.t ?? 0,
    open: agg.o ?? 0,
    high: agg.h ?? 0,
    low: agg.l ?? 0,
    close: agg.c ?? 0,
    volume: agg.v ?? 0,
  };
}

export function normalizeGreeks(g?: PolygonOptionSnapshot["greeks"]): Greeks {
  return {
    delta: g?.delta ?? null,
    gamma: g?.gamma ?? null,
    theta: g?.theta ?? null,
    vega: g?.vega ?? null,
  };
}

export function normalizeOptionContract(snap: PolygonOptionSnapshot): OptionContract {
  const bid = snap.last_quote?.bid ?? 0;
  const ask = snap.last_quote?.ask ?? 0;
  const mid = bid && ask ? (bid + ask) / 2 : 0;

  return {
    ticker: snap.details?.ticker ?? "",
    underlying: snap.underlying_asset?.ticker ?? "",
    expiry: snap.details?.expiration_date ?? "",
    strike: snap.details?.strike_price ?? 0,
    contract_type: (snap.details?.contract_type as "call" | "put") ?? "call",
    bid,
    ask,
    mid,
    last: snap.day?.last?.price ?? snap.day?.close ?? 0,
    volume: snap.day?.volume ?? 0,
    open_interest: snap.day?.open_interest ?? 0,
    implied_volatility: snap.implied_volatility ?? 0,
    greeks: normalizeGreeks(snap.greeks),
  };
}
