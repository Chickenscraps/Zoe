import { useEffect, useMemo, useState } from "react";
import type { Database } from "../lib/types";
import { supabase } from "../lib/supabaseClient";

type HealthHeartbeat = Database["public"]["Tables"]["health_heartbeat"]["Row"];
type AccountOverview = Database["public"]["Functions"]["get_account_overview"]["Returns"][0];
type ActivityFeedItem = Database["public"]["Functions"]["get_activity_feed"]["Returns"][0];
type CryptoCashSnapshot = Database["public"]["Tables"]["crypto_cash_snapshots"]["Row"];
type CryptoHoldingSnapshot = Database["public"]["Tables"]["crypto_holdings_snapshots"]["Row"];
type CryptoReconcileEvent = Database["public"]["Tables"]["crypto_reconciliation_events"]["Row"];
type CryptoOrder = Database["public"]["Tables"]["crypto_orders"]["Row"];
type CryptoFill = Database["public"]["Tables"]["crypto_fills"]["Row"];
type DailyNotional = Database["public"]["Tables"]["daily_notional"]["Row"];

const LIVE_WINDOW_MS = 60_000;

export function useDashboardData(discordId: string = "292890243852664855") {
  const [accountOverview, setAccountOverview] = useState<AccountOverview | null>(null);
  const [recentEvents, setRecentEvents] = useState<ActivityFeedItem[]>([]);
  const [healthStatus, setHealthStatus] = useState<HealthHeartbeat[]>([]);
  const [cryptoCash, setCryptoCash] = useState<CryptoCashSnapshot | null>(null);
  const [cryptoHoldings, setCryptoHoldings] = useState<CryptoHoldingSnapshot | null>(null);
  const [reconcile, setReconcile] = useState<CryptoReconcileEvent | null>(null);
  const [cryptoOrders, setCryptoOrders] = useState<CryptoOrder[]>([]);
  const [cryptoFills, setCryptoFills] = useState<CryptoFill[]>([]);
  const [dailyNotional, setDailyNotional] = useState<DailyNotional | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);

        const [
          overviewRes,
          feedRes,
          healthRes,
          cashRes,
          holdingsRes,
          reconcileRes,
          ordersRes,
          fillsRes,
          dailyNotionalRes,
        ] = await Promise.all([
          supabase.rpc("get_account_overview" as never, { p_discord_id: discordId } as never),
          supabase.rpc("get_activity_feed" as never, { p_limit: 10 } as never),
          supabase.from("health_heartbeat").select("*"),
          supabase
            .from("crypto_cash_snapshots")
            .select("*")
            .order("taken_at", { ascending: false })
            .limit(1)
            .maybeSingle(),
          supabase
            .from("crypto_holdings_snapshots")
            .select("*")
            .order("taken_at", { ascending: false })
            .limit(1)
            .maybeSingle(),
          supabase
            .from("crypto_reconciliation_events")
            .select("*")
            .order("taken_at", { ascending: false })
            .limit(1)
            .maybeSingle(),
          supabase
            .from("crypto_orders")
            .select("*")
            .order("requested_at", { ascending: false })
            .limit(20),
          supabase
            .from("crypto_fills")
            .select("*")
            .order("executed_at", { ascending: false })
            .limit(50),
          supabase
            .from("daily_notional")
            .select("*")
            .eq("day", new Date().toISOString().slice(0, 10))
            .maybeSingle(),
        ]);

        if (overviewRes.data && overviewRes.data.length > 0)
          setAccountOverview(overviewRes.data[0] as AccountOverview);
        if (feedRes.data) setRecentEvents(feedRes.data as ActivityFeedItem[]);
        if (healthRes.data) setHealthStatus(healthRes.data as HealthHeartbeat[]);
        setCryptoCash((cashRes.data ?? null) as CryptoCashSnapshot | null);
        setCryptoHoldings((holdingsRes.data ?? null) as CryptoHoldingSnapshot | null);
        setReconcile((reconcileRes.data ?? null) as CryptoReconcileEvent | null);
        setCryptoOrders((ordersRes.data ?? []) as CryptoOrder[]);
        setCryptoFills((fillsRes.data ?? []) as CryptoFill[]);
        setDailyNotional((dailyNotionalRes.data ?? null) as DailyNotional | null);
      } catch (error) {
        console.error("Error fetching dashboard data:", error);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [discordId]);

  const healthSummary = useMemo(() => {
    const last = reconcile?.taken_at ? Date.parse(reconcile.taken_at) : 0;
    const stale = !last || Date.now() - last > LIVE_WINDOW_MS;
    const status = reconcile?.status === "degraded" || stale ? "DEGRADED" : "LIVE";
    return {
      status,
      stale,
      lastReconcile: reconcile?.taken_at ?? null,
      reason: reconcile?.reason ?? (stale ? "Reconciliation heartbeat stale" : "Healthy"),
    };
  }, [reconcile]);

  const holdingsRows = useMemo(() => {
    const rows = (cryptoHoldings?.holdings as Record<string, number>) || {};
    const total = Object.values(rows).reduce((sum, qty) => sum + Number(qty), 0);
    return Object.entries(rows).map(([asset, qty]) => ({
      asset,
      qty: Number(qty),
      allocation: total > 0 ? (Number(qty) / total) * 100 : 0,
    }));
  }, [cryptoHoldings]);

  const realizedPnl = useMemo(() => {
    return cryptoFills.reduce((sum, fill) => {
      const gross = fill.qty * fill.price;
      return sum + (fill.side === "sell" ? gross : -gross) - fill.fee;
    }, 0);
  }, [cryptoFills]);

  return {
    accountOverview,
    recentEvents,
    healthStatus,
    cryptoCash,
    cryptoHoldings,
    healthSummary,
    holdingsRows,
    cryptoOrders,
    cryptoFills,
    dailyNotional,
    realizedPnl,
    loading,
  };
}
