/**
 * useTradeNotifications — Supabase realtime subscription that fires
 * toast notifications + chime sounds when trades are placed or filled.
 *
 * Subscribes to:
 *   - crypto_orders  (INSERT) → "Order placed" toast
 *   - crypto_fills   (INSERT) → "Order filled" toast
 *   - bounce_events  (INSERT) → "Bounce detected" alert toast
 */

import { useEffect, useRef } from "react";
import { supabase } from "../lib/supabaseClient";
import { useModeContext } from "../lib/mode";
import { chimeBuy, chimeSell, chimeAlert } from "../lib/chime";
import type { ToastAPI, ToastType } from "../components/TradeToast";

export function useTradeNotifications(toastApi: React.MutableRefObject<ToastAPI | null>) {
  const { mode } = useModeContext();
  // Track whether we've received the initial snapshot (skip those)
  const initializedOrders = useRef(false);
  const initializedFills = useRef(false);

  useEffect(() => {
    // Small delay to skip initial data load events
    const initTimer = setTimeout(() => {
      initializedOrders.current = true;
      initializedFills.current = true;
    }, 3000);

    // ── Subscribe to crypto_orders ────────────────────────────────
    const ordersChannel = supabase
      .channel(`trade-notifications-orders-${mode}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "crypto_orders",
          filter: `mode=eq.${mode}`,
        },
        (payload) => {
          if (!initializedOrders.current) return;

          const order = payload.new as Record<string, unknown>;
          const symbol = (order.symbol as string) || "UNKNOWN";
          const side = (order.side as string) || "buy";
          const notional = Number(order.notional ?? 0);
          const status = (order.status as string) || "pending";

          const toastType: ToastType = side === "buy" ? "buy" : "sell";
          const sideLabel = side.toUpperCase();

          // Play chime
          if (side === "buy") {
            chimeBuy();
          } else {
            chimeSell();
          }

          // Push toast
          toastApi.current?.push({
            type: toastType,
            symbol,
            message: `${sideLabel} order ${status} — ${symbol}`,
            amount: notional > 0 ? notional : undefined,
          });
        }
      )
      .subscribe();

    // ── Subscribe to crypto_fills ─────────────────────────────────
    const fillsChannel = supabase
      .channel(`trade-notifications-fills-${mode}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "crypto_fills",
          filter: `mode=eq.${mode}`,
        },
        (payload) => {
          if (!initializedFills.current) return;

          const fill = payload.new as Record<string, unknown>;
          const symbol = (fill.symbol as string) || "UNKNOWN";
          const side = (fill.side as string) || "buy";
          const qty = Number(fill.qty ?? 0);
          const price = Number(fill.price ?? 0);
          const total = qty * price;

          const toastType: ToastType = side === "buy" ? "buy" : "sell";

          // Play chime
          if (side === "buy") {
            chimeBuy();
          } else {
            chimeSell();
          }

          // Push toast
          toastApi.current?.push({
            type: toastType,
            symbol,
            message: `Filled: ${side.toUpperCase()} ${qty.toFixed(6)} @ $${price.toLocaleString()}`,
            amount: total > 0 ? total : undefined,
          });
        }
      )
      .subscribe();

    // ── Subscribe to bounce_events (structure pipeline alerts) ────
    const bounceChannel = supabase
      .channel(`trade-notifications-bounce-${mode}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "bounce_events",
          filter: `mode=eq.${mode}`,
        },
        (payload) => {
          const event = payload.new as Record<string, unknown>;
          const symbol = (event.symbol as string) || "CRYPTO";
          const phase = (event.phase as string) || "detection";

          chimeAlert();

          toastApi.current?.push({
            type: "alert",
            symbol,
            message: `Bounce ${phase} detected`,
          });
        }
      )
      .subscribe();

    // ── Subscribe to structure_events (breakout/breakdown) ────────
    const structureChannel = supabase
      .channel(`trade-notifications-structure-${mode}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "structure_events",
          filter: `mode=eq.${mode}`,
        },
        (payload) => {
          const event = payload.new as Record<string, unknown>;
          const symbol = (event.symbol as string) || "CRYPTO";
          const eventType = (event.event_type as string) || "event";

          chimeAlert();

          toastApi.current?.push({
            type: "alert",
            symbol,
            message: `Structure ${eventType} confirmed`,
          });
        }
      )
      .subscribe();

    return () => {
      clearTimeout(initTimer);
      supabase.removeChannel(ordersChannel);
      supabase.removeChannel(fillsChannel);
      supabase.removeChannel(bounceChannel);
      supabase.removeChannel(structureChannel);
    };
  }, [toastApi, mode]);
}
