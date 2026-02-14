/**
 * useMarketSnapshots — Realtime subscription on market_snapshot_focus
 * for sub-second live price updates in the dashboard.
 *
 * Falls back to polling every 2s if realtime channel fails.
 * Returns a map of symbol → snapshot row.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { supabase, supabaseMisconfigured } from "../lib/supabaseClient";
import type { Database } from "../lib/types";

type FocusSnapshot = Database["public"]["Tables"]["market_snapshot_focus"]["Row"];

export interface MarketSnapshotsResult {
  /** Map of symbol → latest focus snapshot */
  snapshots: Record<string, FocusSnapshot>;
  /** Flat array of all snapshots, sorted by symbol */
  snapshotsList: FocusSnapshot[];
  /** Whether the initial load is in progress */
  loading: boolean;
  /** Last update timestamp (ISO string) from the most recent snapshot */
  lastUpdated: string | null;
}

const FALLBACK_POLL_MS = 2_000;

export function useMarketSnapshots(): MarketSnapshotsResult {
  const [snapshots, setSnapshots] = useState<Record<string, FocusSnapshot>>({});
  const [loading, setLoading] = useState(true);
  const realtimeActive = useRef(false);

  // Full fetch from market_snapshot_focus
  const fetchAll = useCallback(async () => {
    if (supabaseMisconfigured) return;
    try {
      const { data, error } = await supabase
        .from("market_snapshot_focus")
        .select("*")
        .order("symbol", { ascending: true });

      if (error) {
        console.error("market_snapshot_focus fetch error:", error.message);
        return;
      }
      if (data) {
        const map: Record<string, FocusSnapshot> = {};
        for (const row of data as FocusSnapshot[]) {
          map[row.symbol] = row;
        }
        setSnapshots(map);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Initial fetch
    fetchAll();

    // Realtime subscription for INSERT/UPDATE on market_snapshot_focus
    const channel = supabase
      .channel("market-snapshots-focus-rt")
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "market_snapshot_focus",
        },
        (payload) => {
          realtimeActive.current = true;
          const row = payload.new as FocusSnapshot;
          if (row && row.symbol) {
            setSnapshots((prev) => ({ ...prev, [row.symbol]: row }));
          }
        }
      )
      .subscribe((status) => {
        if (status === "SUBSCRIBED") {
          realtimeActive.current = true;
        }
      });

    // Fallback polling in case realtime doesn't fire
    const pollInterval = setInterval(() => {
      if (!realtimeActive.current) {
        fetchAll();
      }
      // Reset flag — if realtime is working it'll set it back to true
      realtimeActive.current = false;
    }, FALLBACK_POLL_MS);

    return () => {
      clearInterval(pollInterval);
      supabase.removeChannel(channel);
    };
  }, [fetchAll]);

  // Derived: sorted list + last updated
  const snapshotsList = Object.values(snapshots).sort((a, b) =>
    a.symbol.localeCompare(b.symbol)
  );
  const lastUpdated =
    snapshotsList.length > 0
      ? snapshotsList.reduce((latest, s) =>
          s.updated_at > latest.updated_at ? s : latest
        ).updated_at
      : null;

  return { snapshots, snapshotsList, loading, lastUpdated };
}
