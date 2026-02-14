import { useEffect, useRef } from "react";
import { supabase, supabaseMisconfigured } from "../lib/supabaseClient";
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
  const channelRef = useRef<RealtimeChannel | null>(null);

  useEffect(() => {
    if (supabaseMisconfigured) return;

    const channel = supabase
      .channel("dashboard-live")
      // Order status changes (insert + update) → refresh orders immediately
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "crypto_orders",
        },
        () => callbacks.onOrderChange()
      )
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "crypto_orders",
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
        },
        () => callbacks.onOrderChange()
      )
      .subscribe((status) => {
        if (status === "SUBSCRIBED") {
          console.log("[ZOE] Realtime connected");
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
  }, []);
}
