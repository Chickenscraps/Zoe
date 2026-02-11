import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
const POLL_INTERVAL_MS = 30_000;

export interface EquityPoint {
  date: string;
  equity: number;
}

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
  const [cashHistory, setCashHistory] = useState<CryptoCashSnapshot[]>([]);
  const [pnlDaily, setPnlDaily] = useState<PnlDaily[]>([]);
  const [livePrices, setLivePrices] = useState<CandidateScan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async (isInitial = false) => {
    try {
      if (isInitial) setLoading(true);
      if (supabaseMisconfigured) {
        setError("Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY. Copy .env.example to .env and configure.");
        return;
      }

      const [
        overviewRes,
        feedRes,
        healthRes,
        cashRes,
        cashHistoryRes,
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
        // Fetch full cash snapshot history for equity chart (last 90 days)
        supabase
          .from("crypto_cash_snapshots")
          .select("*")
          .eq("mode", MODE)
          .order("taken_at", { ascending: true })
          .gte("taken_at", new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString())
          .limit(500),
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
      setCashHistory((cashHistoryRes.data ?? []) as CryptoCashSnapshot[]);
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
      if (isInitial) setLoading(false);
    }
  }, [discordId]);

  // Initial fetch + polling every 30s
  useEffect(() => {
    fetchData(true);

    pollRef.current = setInterval(() => fetchData(false), POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchData]);

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

  // Build equity history from cash snapshots, or fallback to running P&L from fills
  const equityHistory = useMemo((): EquityPoint[] => {
    // Primary source: crypto_cash_snapshots history (real Robinhood truth data)
    if (cashHistory.length > 0) {
      // Deduplicate by date (keep latest snapshot per day)
      const byDay = new Map<string, number>();
      for (const snap of cashHistory) {
        const day = snap.taken_at.slice(0, 10);
        byDay.set(day, snap.cash_available + (snap.buying_power - snap.cash_available));
      }
      return Array.from(byDay.entries())
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([date, equity]) => ({ date, equity }));
    }

    // Fallback: compute running equity from fills (starting from buying power or $100k paper)
    if (cryptoFills.length > 0) {
      const startingEquity = cryptoCash?.buying_power ?? 100_000;
      // Fills are newest-first, reverse for chronological order
      const chronFills = [...cryptoFills].reverse();
      let runningEquity = startingEquity;
      const points: EquityPoint[] = [
        { date: chronFills[0].executed_at.slice(0, 10), equity: startingEquity },
      ];
      for (const fill of chronFills) {
        const gross = fill.qty * fill.price;
        const delta = (fill.side === "sell" ? gross : -gross) - fill.fee;
        runningEquity += delta;
        points.push({
          date: fill.executed_at.slice(0, 10),
          equity: runningEquity,
        });
      }
      // Deduplicate by date (keep last per day)
      const byDay = new Map<string, number>();
      for (const pt of points) {
        byDay.set(pt.date, pt.equity);
      }
      return Array.from(byDay.entries())
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([date, equity]) => ({ date, equity }));
    }

    return [];
  }, [cashHistory, cryptoFills, cryptoCash]);

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
    equityHistory,
    livePrices,
    loading,
    error,
  };
}
