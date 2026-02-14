import { useState, useEffect, useCallback } from "react";
import { supabase } from "../lib/supabaseClient";
import type { Database } from "../lib/types";

type FocusRow = Database["public"]["Tables"]["market_snapshot_focus"]["Row"];
type ScoutRow = Database["public"]["Tables"]["market_snapshot_scout"]["Row"];
type MoverRow = Database["public"]["Tables"]["mover_events"]["Row"];
type CatalogRow = Database["public"]["Tables"]["market_catalog"]["Row"];

/** Merged market row for the Markets table. */
export interface MarketRow {
  symbol: string;
  base: string;
  bid: number;
  ask: number;
  mid: number;
  spread_pct: number;
  volume_24h: number;
  change_24h_pct: number;
  vwap: number;
  high_24h: number;
  low_24h: number;
  updated_at: string;
  is_focus: boolean;
  exchange: string;
}

const SCOUT_POLL_MS = 30_000;

/**
 * Hook for the focus universe — uses Supabase realtime for live updates.
 */
export function useFocusData() {
  const [data, setData] = useState<FocusRow[]>([]);
  const [loading, setLoading] = useState(true);

  // Initial fetch
  useEffect(() => {
    const fetch = async () => {
      const { data: rows } = await supabase
        .from("market_snapshot_focus")
        .select("*")
        .order("symbol");
      if (rows) setData(rows);
      setLoading(false);
    };
    fetch();
  }, []);

  // Realtime subscription
  useEffect(() => {
    const channel = supabase
      .channel("focus-realtime")
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "market_snapshot_focus",
        },
        (payload) => {
          const row = payload.new as FocusRow;
          if (!row?.symbol) return;
          setData((prev) => {
            const idx = prev.findIndex((r) => r.symbol === row.symbol);
            if (idx >= 0) {
              const next = [...prev];
              next[idx] = row;
              return next;
            }
            return [...prev, row];
          });
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  return { data, loading };
}

/**
 * Hook for the scout universe — polls every 30 seconds.
 */
export function useScoutData() {
  const [data, setData] = useState<ScoutRow[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    const { data: rows } = await supabase
      .from("market_snapshot_scout")
      .select("*")
      .order("symbol");
    if (rows) setData(rows);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetch();
    const interval = setInterval(fetch, SCOUT_POLL_MS);
    return () => clearInterval(interval);
  }, [fetch]);

  return { data, loading };
}

/**
 * Hook for mover alerts — realtime subscription.
 */
export function useMoverAlerts(limit = 20) {
  const [events, setEvents] = useState<MoverRow[]>([]);

  // Initial fetch
  useEffect(() => {
    const fetch = async () => {
      const { data: rows } = await supabase
        .from("mover_events")
        .select("*")
        .order("detected_at", { ascending: false })
        .limit(limit);
      if (rows) setEvents(rows);
    };
    fetch();
  }, [limit]);

  // Realtime
  useEffect(() => {
    const channel = supabase
      .channel("movers-realtime")
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "mover_events",
        },
        (payload) => {
          const row = payload.new as MoverRow;
          setEvents((prev) => [row, ...prev].slice(0, limit));
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [limit]);

  return events;
}

/**
 * Combined hook: merges focus + scout into a single MarketRow[] for the Markets table.
 */
export function useMarketData() {
  const { data: focusData, loading: focusLoading } = useFocusData();
  const { data: scoutData, loading: scoutLoading } = useScoutData();
  const [catalog, setCatalog] = useState<Map<string, CatalogRow>>(new Map());

  // Load catalog once
  useEffect(() => {
    const fetch = async () => {
      const { data: rows } = await supabase
        .from("market_catalog")
        .select("symbol, base, exchange")
        .eq("status", "active");
      if (rows) {
        const map = new Map<string, CatalogRow>();
        for (const r of rows) map.set(r.symbol, r as CatalogRow);
        setCatalog(map);
      }
    };
    fetch();
  }, []);

  const focusSymbols = new Set(focusData.map((r) => r.symbol));

  const rows: MarketRow[] = [
    // Focus rows (full data)
    ...focusData.map((r) => ({
      symbol: r.symbol,
      base: catalog.get(r.symbol)?.base ?? r.symbol.split("-")[0],
      bid: r.bid,
      ask: r.ask,
      mid: r.mid,
      spread_pct: r.spread_pct,
      volume_24h: r.volume_24h,
      change_24h_pct: r.change_24h_pct,
      vwap: r.vwap,
      high_24h: r.high_24h,
      low_24h: r.low_24h,
      updated_at: r.updated_at,
      is_focus: true,
      exchange: catalog.get(r.symbol)?.exchange ?? "kraken",
    })),
    // Scout rows (subset of fields, not in focus)
    ...scoutData
      .filter((r) => !focusSymbols.has(r.symbol))
      .map((r) => ({
        symbol: r.symbol,
        base: catalog.get(r.symbol)?.base ?? r.symbol.split("-")[0],
        bid: r.bid,
        ask: r.ask,
        mid: r.mid,
        spread_pct: 0,
        volume_24h: r.volume_24h,
        change_24h_pct: r.change_24h_pct,
        vwap: 0,
        high_24h: 0,
        low_24h: 0,
        updated_at: r.updated_at,
        is_focus: false,
        exchange: catalog.get(r.symbol)?.exchange ?? "kraken",
      })),
  ];

  return {
    rows,
    loading: focusLoading || scoutLoading,
    focusCount: focusData.length,
    scoutCount: scoutData.length,
  };
}
