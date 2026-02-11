import { useEffect, useMemo, useState } from "react";
import type { Database } from "../lib/types";
import { supabase, supabaseMisconfigured } from "../lib/supabaseClient";
import { MODE } from "../lib/mode";

type HealthHeartbeat = Database["public"]["Tables"]["health_heartbeat"]["Row"];
type AccountOverview = Database["public"]["Functions"]["get_account_overview"]["Returns"][0];
type ActivityFeedItem = Database["public"]["Functions"]["get_activity_feed"]["Returns"][0];
type CryptoCashSnapshot = Database["public"]["Tables"]["crypto_cash_snapshots"]["Row"];
type CryptoHoldingSnapshot = Database["public"]["Tables"]["crypto_holdings_snapshots"]["Row"];
type CryptoReconcileEvent = Database["public"]["Tables"]["crypto_reconciliation_events"]["Row"];
type CryptoOrder = Database["public"]["Tables"]["crypto_orders"]["Row"];
type CryptoFill = Database["public"]["Tables"]["crypto_fills"]["Row"];
type DailyNotional = Database["public"]["Tables"]["daily_notional"]["Row"];
type PnlDaily = Database["public"]["Tables"]["pnl_daily"]["Row"];
type CandidateScan = Database["public"]["Tables"]["candidate_scans"]["Row"];

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
  const [pnlDaily, setPnlDaily] = useState<PnlDaily[]>([]);
  const [livePrices, setLivePrices] = useState<CandidateScan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        if (supabaseMisconfigured) {
          setError("Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY. Copy .env.example to .env and configure.");
          return;
        }

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
          pnlDailyRes,
          livePricesRes,
        ] = await Promise.all([
          supabase.rpc("get_account_overview" as never, { p_discord_id: discordId } as never),
          supabase.rpc("get_activity_feed" as never, { p_limit: 10 } as never),
          supabase.from("health_heartbeat").select("*").eq("mode", MODE),
          supabase
            .from("crypto_cash_snapshots")
            .select("*")
            .eq("mode", MODE)
            .order("taken_at", { ascending: false })
            .limit(1)
            .maybeSingle(),
          supabase
            .from("crypto_holdings_snapshots")
            .select("*")
            .eq("mode", MODE)
            .order("taken_at", { ascending: false })
            .limit(1)
            .maybeSingle(),
          supabase
            .from("crypto_reconciliation_events")
            .select("*")
            .eq("mode", MODE)
            .order("taken_at", { ascending: false })
            .limit(1)
            .maybeSingle(),
          supabase
            .from("crypto_orders")
            .select("*")
            .eq("mode", MODE)
            .order("requested_at", { ascending: false })
            .limit(20),
          supabase
            .from("crypto_fills")
            .select("*")
            .eq("mode", MODE)
            .order("executed_at", { ascending: false })
            .limit(50),
          supabase
            .from("daily_notional")
            .select("*")
            .eq("mode", MODE)
            .eq("day", new Date().toISOString().slice(0, 10))
            .maybeSingle(),
          supabase
            .from("pnl_daily")
            .select("date, equity, daily_pnl")
            .eq("mode", MODE)
            .order("date", { ascending: true })
            .limit(90),
          // Latest scan batch for live prices
          (async () => {
            const { data: latest } = await supabase
              .from("candidate_scans")
              .select("created_at")
              .eq("mode", MODE)
              .order("created_at", { ascending: false })
              .limit(1)
              .maybeSingle();
            if (!latest?.created_at) return { data: [], error: null };
            return supabase
              .from("candidate_scans")
              .select("*")
              .eq("mode", MODE)
              .eq("created_at", latest.created_at)
              .order("score", { ascending: false });
          })(),
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
        setPnlDaily((pnlDailyRes.data ?? []) as PnlDaily[]);
        setLivePrices((livePricesRes.data ?? []) as CandidateScan[]);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        console.error("Error fetching dashboard data:", msg);
        setError(msg);
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
    pnlDaily,
    realizedPnl,
    livePrices,
    loading,
    error,
  };
}
