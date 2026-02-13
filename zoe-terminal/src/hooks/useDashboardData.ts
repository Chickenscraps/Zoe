import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Database } from "../lib/types";
import { supabase, supabaseMisconfigured } from "../lib/supabaseClient";

type HealthHeartbeat = Database["public"]["Tables"]["health_heartbeat"]["Row"];
type AccountOverview = Database["public"]["Functions"]["get_account_overview"]["Returns"][0];
type ActivityFeedItem = Database["public"]["Functions"]["get_activity_feed"]["Returns"][0];
type CryptoCashSnapshot = Database["public"]["Tables"]["crypto_cash_snapshots"]["Row"];
type CryptoHoldingSnapshot = Database["public"]["Tables"]["crypto_holdings_snapshots"]["Row"];
type CryptoOrder = Database["public"]["Tables"]["crypto_orders"]["Row"];
type CryptoFill = Database["public"]["Tables"]["crypto_fills"]["Row"];
type DailyNotional = Database["public"]["Tables"]["daily_notional"]["Row"];
type PnlDaily = Database["public"]["Tables"]["pnl_daily"]["Row"];
type CandidateScan = Database["public"]["Tables"]["candidate_scans"]["Row"];

const LIVE_WINDOW_MS = 60_000;
const POLL_INTERVAL_MS = 30_000;
const PRICE_POLL_MS = 5_000; // fast poll just for live prices

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
        ordersRes,
        fillsRes,
        dailyNotionalRes,
        pnlDailyRes,
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
        // Fetch full cash snapshot history for equity chart (last 90 days, high-res for 5-min chart)
        supabase
          .from("crypto_cash_snapshots")
          .select("*")
          .order("taken_at", { ascending: true })
          .gte("taken_at", new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString())
          .limit(2000),
        supabase
          .from("crypto_holdings_snapshots")
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
        supabase
          .from("pnl_daily")
          .select("date, equity, daily_pnl")
          .order("date", { ascending: true })
          .limit(90),
      ]);

      // Fetch latest scan batch for live prices (separate to avoid Promise.all type issues)
      const livePricesRes = await (async () => {
        const { data: latest } = await supabase
          .from("candidate_scans")
          .select("created_at")
          .order("created_at", { ascending: false })
          .limit(1)
          .maybeSingle();
        if (!latest?.created_at) return { data: [] as CandidateScan[] };
        return supabase
          .from("candidate_scans")
          .select("*")
          .eq("created_at", latest.created_at)
          .order("score", { ascending: false });
      })();

      const overviewData = (overviewRes as any).data;
      const feedData = (feedRes as any).data;
      if (overviewData && overviewData.length > 0)
        setAccountOverview(overviewData[0] as AccountOverview);
      if (feedData) setRecentEvents(feedData as ActivityFeedItem[]);
      if (healthRes.data) setHealthStatus(healthRes.data as HealthHeartbeat[]);
      setCryptoCash((cashRes.data ?? null) as CryptoCashSnapshot | null);
      setCashHistory((cashHistoryRes.data ?? []) as CryptoCashSnapshot[]);
      setCryptoHoldings((holdingsRes.data ?? null) as CryptoHoldingSnapshot | null);
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

  // Fast price-only fetch (every 5s)
  const fetchPrices = useCallback(async () => {
    try {
      const { data: latest } = await supabase
        .from("candidate_scans")
        .select("created_at")
        .order("created_at", { ascending: false })
        .limit(1)
        .maybeSingle();
      if (!latest?.created_at) return;
      const { data } = await supabase
        .from("candidate_scans")
        .select("*")
        .eq("created_at", latest.created_at)
        .order("score", { ascending: false });
      if (data) setLivePrices(data as CandidateScan[]);
    } catch {
      // non-fatal
    }
  }, []);

  // Initial fetch + full dashboard polling every 30s + fast price polling every 5s
  useEffect(() => {
    fetchData(true);

    pollRef.current = setInterval(() => fetchData(false), POLL_INTERVAL_MS);
    const priceInterval = setInterval(fetchPrices, PRICE_POLL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      clearInterval(priceInterval);
    };
  }, [fetchData, fetchPrices]);

  // Health summary derived from heartbeat data
  const healthSummary = useMemo(() => {
    const liveServices = healthStatus.filter(
      h => new Date(h.last_heartbeat).getTime() > Date.now() - LIVE_WINDOW_MS,
    );
    const stale = liveServices.length === 0;
    const hasError = healthStatus.some(h => h.status === "error" || h.status === "down");
    const status = hasError ? "DEGRADED" : stale ? "DEGRADED" : "LIVE";
    return {
      status,
      stale,
      lastReconcile: liveServices.length > 0 ? liveServices[0].last_heartbeat : null,
      reason: hasError ? "Service degraded" : stale ? "No recent heartbeats" : "Healthy",
    };
  }, [healthStatus]);

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
    // Compute realized P&L from matched buy→sell round-trips only.
    // Build cost basis per symbol from buys, then calculate profit on sells.
    const costBasis: Record<string, { totalCost: number; totalQty: number }> = {};
    // Sort by executed_at ascending so we process buys before sells
    const sorted = [...cryptoFills].sort((a, b) =>
      (a.executed_at ?? "").localeCompare(b.executed_at ?? "")
    );
    let realized = 0;
    for (const fill of sorted) {
      const sym = fill.symbol;
      if (fill.side === "buy") {
        if (!costBasis[sym]) costBasis[sym] = { totalCost: 0, totalQty: 0 };
        costBasis[sym].totalCost += fill.qty * fill.price + fill.fee;
        costBasis[sym].totalQty += fill.qty;
      } else if (fill.side === "sell") {
        const basis = costBasis[sym];
        if (basis && basis.totalQty > 0) {
          const avgCost = basis.totalCost / basis.totalQty;
          const sellProceeds = fill.qty * fill.price - fill.fee;
          const costOfSold = fill.qty * avgCost;
          realized += sellProceeds - costOfSold;
          // Reduce basis by qty sold
          basis.totalCost -= costOfSold;
          basis.totalQty -= fill.qty;
          if (basis.totalQty <= 0) {
            basis.totalCost = 0;
            basis.totalQty = 0;
          }
        } else {
          // No buy basis found — treat sell proceeds minus fee as pure realized
          realized += fill.qty * fill.price - fill.fee;
        }
      }
    }
    return realized;
  }, [cryptoFills]);

  // Build equity history from cash snapshots at 5-minute granularity.
  // Each snapshot keeps its full timestamp (bucketed to nearest 5 min).
  // Current crypto holdings value is added to all non-initial points.
  const equityHistory = useMemo((): EquityPoint[] => {
    if (cashHistory.length > 0) {
      // Bucket snapshots into 5-minute intervals (use latest value per bucket)
      const BUCKET_MS = 5 * 60 * 1000; // 5 minutes
      const byBucket = new Map<number, { ts: number; cash: number }>();
      for (const snap of cashHistory) {
        const ts = new Date(snap.taken_at).getTime();
        const bucket = Math.floor(ts / BUCKET_MS) * BUCKET_MS;
        // Keep latest snapshot per bucket
        const existing = byBucket.get(bucket);
        if (!existing || ts > existing.ts) {
          byBucket.set(bucket, { ts, cash: snap.buying_power });
        }
      }

      const currentCryptoVal = holdingsRows.reduce((sum, row) => {
        const scan = livePrices.find(s => s.symbol === row.asset);
        const mid = scan ? ((scan.info as any)?.mid ?? 0) : 0;
        return sum + row.qty * mid;
      }, 0);

      const sorted = Array.from(byBucket.entries()).sort((a, b) => a[0] - b[0]);
      const points = sorted.map(([_bucket, { cash }], idx) => ({
        date: new Date(_bucket).toISOString(),
        // First point = initial deposit (no crypto yet), rest add current crypto value
        equity: idx === 0 ? cash : cash + currentCryptoVal,
      }));

      // If only 1 point but we have crypto holdings, add a "now" point
      if (points.length === 1 && currentCryptoVal > 0) {
        points.push({
          date: new Date().toISOString(),
          equity: sorted[sorted.length - 1][1].cash + currentCryptoVal,
        });
      }

      return points;
    }

    // Fallback: pnl_daily (lower granularity)
    if (pnlDaily.length > 0) {
      return pnlDaily.map(row => ({
        date: row.date,
        equity: row.equity,
      }));
    }

    return [];
  }, [cashHistory, pnlDaily, holdingsRows, livePrices]);

  // Initial deposit = first cash snapshot buying_power (before any trades)
  const initialDeposit = useMemo(() => {
    if (cashHistory.length > 0) return cashHistory[0].buying_power;
    if (pnlDaily.length > 0) return pnlDaily[0].equity;
    return 0;
  }, [cashHistory, pnlDaily]);

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
    initialDeposit,
    livePrices,
    loading,
    error,
  };
}
