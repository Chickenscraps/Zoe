/**
 * useStructureData — fetches trendlines, levels, pivots, events, and bounce state from Supabase.
 *
 * Polls every 30s and supports per-symbol + per-timeframe filtering.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { Database } from "../lib/types";
import { supabase } from "../lib/supabaseClient";
import { useModeContext } from "../lib/mode";

type MarketPivot = Database["public"]["Tables"]["market_pivots"]["Row"];
type TechnicalTrendline = Database["public"]["Tables"]["technical_trendlines"]["Row"];
type TechnicalLevel = Database["public"]["Tables"]["technical_levels"]["Row"];
type StructureEvent = Database["public"]["Tables"]["structure_events"]["Row"];
type BounceEvent = Database["public"]["Tables"]["bounce_events"]["Row"];
type BounceIntent = Database["public"]["Tables"]["bounce_intents"]["Row"];

export type { MarketPivot, TechnicalTrendline, TechnicalLevel, StructureEvent, BounceEvent, BounceIntent };

const POLL_INTERVAL_MS = 30_000;

export interface StructureFilters {
  symbol?: string;
  timeframe?: string;
}

export function useStructureData(filters: StructureFilters = {}) {
  const { mode } = useModeContext();
  const [pivots, setPivots] = useState<MarketPivot[]>([]);
  const [trendlines, setTrendlines] = useState<TechnicalTrendline[]>([]);
  const [levels, setLevels] = useState<TechnicalLevel[]>([]);
  const [structureEvents, setStructureEvents] = useState<StructureEvent[]>([]);
  const [bounceEvents, setBounceEvents] = useState<BounceEvent[]>([]);
  const [bounceIntents, setBounceIntents] = useState<BounceIntent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async (isInitial = false) => {
    try {
      if (isInitial) setLoading(true);
      setError(null);

      // Build filtered queries (always scoped to current mode)
      let pivotQuery = supabase
        .from("market_pivots")
        .select("*")
        .eq("mode", mode)
        .order("timestamp", { ascending: false })
        .limit(100);

      let trendlineQuery = supabase
        .from("technical_trendlines")
        .select("*")
        .eq("mode", mode)
        .eq("is_active", true)
        .order("score", { ascending: false })
        .limit(50);

      let levelQuery = supabase
        .from("technical_levels")
        .select("*")
        .eq("mode", mode)
        .eq("is_active", true)
        .order("score", { ascending: false })
        .limit(50);

      let eventQuery = supabase
        .from("structure_events")
        .select("*")
        .eq("mode", mode)
        .order("ts", { ascending: false })
        .limit(30);

      let bounceEventQuery = supabase
        .from("bounce_events")
        .select("*")
        .eq("mode", mode)
        .order("ts", { ascending: false })
        .limit(30);

      let bounceIntentQuery = supabase
        .from("bounce_intents")
        .select("*")
        .eq("mode", mode)
        .order("ts", { ascending: false })
        .limit(20);

      // Apply symbol filter
      if (filters.symbol) {
        pivotQuery = pivotQuery.eq("symbol", filters.symbol);
        trendlineQuery = trendlineQuery.eq("symbol", filters.symbol);
        levelQuery = levelQuery.eq("symbol", filters.symbol);
        eventQuery = eventQuery.eq("symbol", filters.symbol);
        bounceEventQuery = bounceEventQuery.eq("symbol", filters.symbol);
        bounceIntentQuery = bounceIntentQuery.eq("symbol", filters.symbol);
      }

      // Apply timeframe filter (not applicable to bounce tables)
      if (filters.timeframe) {
        pivotQuery = pivotQuery.eq("timeframe", filters.timeframe);
        trendlineQuery = trendlineQuery.eq("timeframe", filters.timeframe);
        levelQuery = levelQuery.eq("timeframe", filters.timeframe);
        eventQuery = eventQuery.eq("timeframe", filters.timeframe);
      }

      const [
        pivotRes,
        trendlineRes,
        levelRes,
        eventRes,
        bounceEventRes,
        bounceIntentRes,
      ] = await Promise.all([
        pivotQuery,
        trendlineQuery,
        levelQuery,
        eventQuery,
        bounceEventQuery,
        bounceIntentQuery,
      ]);

      setPivots((pivotRes.data ?? []) as MarketPivot[]);
      setTrendlines((trendlineRes.data ?? []) as TechnicalTrendline[]);
      setLevels((levelRes.data ?? []) as TechnicalLevel[]);
      setStructureEvents((eventRes.data ?? []) as StructureEvent[]);
      setBounceEvents((bounceEventRes.data ?? []) as BounceEvent[]);
      setBounceIntents((bounceIntentRes.data ?? []) as BounceIntent[]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error("Error fetching structure data:", msg);
      setError(msg);
    } finally {
      if (isInitial) setLoading(false);
    }
  }, [filters.symbol, filters.timeframe, mode]);

  useEffect(() => {
    fetchData(true);

    pollRef.current = setInterval(() => fetchData(false), POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchData]);

  return {
    pivots,
    trendlines,
    levels,
    structureEvents,
    bounceEvents,
    bounceIntents,
    loading,
    error,
  };
}
