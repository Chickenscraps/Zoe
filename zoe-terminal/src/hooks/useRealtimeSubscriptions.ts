import { useEffect, useRef } from "react";
import { supabase, supabaseMisconfigured } from "../lib/supabaseClient";
import { useModeContext } from "../lib/mode";
import type { RealtimeChannel } from "@supabase/supabase-js";

interface RealtimeCallbacks {
  onOrderChange: () => void;
  onPriceChange: () => void;
  onCashChange: () => void;
  onFillChange: () => void;
}

/**
 * Subscribes to Supabase Realtime channels for near-instant dashboard updates.
 * Falls back to polling if WebSocket disconnects.
 */
export function useRealtimeSubscriptions(callbacks: RealtimeCallbacks) {
  const { mode } = useModeContext();
  const channelRef = useRef<RealtimeChannel | null>(null);

  useEffect(() => {
    if (supabaseMisconfigured) return;

    const channel = supabase
      .channel(`dashboard-${mode}`)
      // Order status changes (insert + update) → refresh orders immediately
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "crypto_orders",
          filter: `mode=eq.${mode}`,
        },
        () => callbacks.onOrderChange()
      )
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "crypto_orders",
          filter: `mode=eq.${mode}`,
        },
        () => callbacks.onOrderChange()
      )
      // New fills → refresh fills + orders
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "crypto_fills",
          filter: `mode=eq.${mode}`,
        },
        () => callbacks.onFillChange()
      )
      // New scan batch → refresh live prices
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "candidate_scans",
          filter: `mode=eq.${mode}`,
        },
        () => callbacks.onPriceChange()
      )
      // New cash snapshot → refresh cash/equity
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "crypto_cash_snapshots",
          filter: `mode=eq.${mode}`,
        },
        () => callbacks.onCashChange()
      )
      // Order events → refresh orders (lifecycle transitions)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "order_events",
          filter: `mode=eq.${mode}`,
        },
        () => callbacks.onOrderChange()
      )
      .subscribe((status) => {
        if (status === "SUBSCRIBED") {
          console.log("[ZOE] Realtime connected for mode:", mode);
        }
        if (status === "CHANNEL_ERROR" || status === "TIMED_OUT") {
          console.warn("[ZOE] Realtime channel error, falling back to polling");
        }
      });

    channelRef.current = channel;

    return () => {
      if (channelRef.current) {
        supabase.removeChannel(channelRef.current);
        channelRef.current = null;
      }
    };
  }, [mode]); // Only re-subscribe when mode changes
}
