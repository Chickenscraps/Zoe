import { useEffect, useState } from "react";
import { Activity, DollarSign, TrendingUp, ShieldCheck, Zap } from "lucide-react";
import { EquityChart } from "../components/EquityChart";
import { KPICard } from "../components/KPICard";
import { Skeleton } from "../components/Skeleton";
import { StatusChip } from "../components/StatusChip";
import { useDashboardData } from "../hooks/useDashboardData";
import { formatCurrency, formatPercentage, cn } from "../lib/utils";
import { supabase } from "../lib/supabaseClient";

interface EfPosition {
  id: string;
  symbol: string;
  side: string;
  entry_price: number;
  size_usd: number;
  status: string;
  pnl_usd: number | null;
  exit_time: string | null;
  created_at: string;
}

interface EfRegime {
  regime: string;
  confidence: number;
  detected_at: string;
}

function useEdgeFactoryData() {
  const [positions, setPositions] = useState<EfPosition[]>([]);
  const [regime, setRegime] = useState<EfRegime | null>(null);
  const [pnlData, setPnlData] = useState<{ date: string; equity: number; daily_pnl: number }[]>([]);

  useEffect(() => {
    async function fetchEf() {
      // Latest regime
      const regimeRes = await supabase
        .from("ef_regimes")
        .select("regime, confidence, detected_at")
        .order("detected_at", { ascending: false })
        .limit(1)
        .maybeSingle();
      if (regimeRes.data) setRegime(regimeRes.data as EfRegime);

      // Recent positions (open + closed)
      const posRes = await supabase
        .from("ef_positions")
        .select("id, symbol, side, entry_price, size_usd, status, pnl_usd, exit_time, created_at")
        .order("created_at", { ascending: false })
        .limit(50);
      if (posRes.data) setPositions(posRes.data as EfPosition[]);

      // Build equity curve from closed positions
      const closedRes = await supabase
        .from("ef_positions")
        .select("pnl_usd, exit_time")
        .not("pnl_usd", "is", null)
        .not("exit_time", "is", null)
        .order("exit_time", { ascending: true });

      if (closedRes.data && closedRes.data.length > 0) {
        const BASE_EQUITY = 150.0;
        let runningEquity = BASE_EQUITY;
        const dailyMap = new Map<string, { equity: number; daily_pnl: number }>();

        for (const pos of closedRes.data) {
          const day = (pos.exit_time as string).slice(0, 10);
          const pnl = pos.pnl_usd as number;
          runningEquity += pnl;

          const existing = dailyMap.get(day);
          if (existing) {
            existing.equity = runningEquity;
            existing.daily_pnl += pnl;
          } else {
            dailyMap.set(day, { equity: runningEquity, daily_pnl: pnl });
          }
        }

        const curve = Array.from(dailyMap.entries()).map(([date, vals]) => ({
          date,
          equity: parseFloat(vals.equity.toFixed(2)),
          daily_pnl: parseFloat(vals.daily_pnl.toFixed(4)),
        }));

        setPnlData(curve);
      }
    }

    fetchEf();
  }, []);

  const openPositions = positions.filter(p => p.status === "open" || p.status === "pending");
  const closedPositions = positions.filter(p => p.status !== "open" && p.status !== "pending");
  const totalPnl = closedPositions.reduce((sum, p) => sum + (p.pnl_usd ?? 0), 0);
  const wins = closedPositions.filter(p => (p.pnl_usd ?? 0) > 0).length;
  const losses = closedPositions.filter(p => (p.pnl_usd ?? 0) <= 0).length;

  return { positions, openPositions, closedPositions, regime, pnlData, totalPnl, wins, losses };
}

export default function Overview() {
  const {
    accountOverview,
    recentEvents,
    healthStatus,
    cryptoCash,
    holdingsRows,
    healthSummary,
    dailyNotional,
    realizedPnl,
    cryptoOrders,
    loading,
  } = useDashboardData();

  const ef = useEdgeFactoryData();

  const equity = accountOverview?.equity ?? 0;
  const todayPnl = accountOverview?.day_pnl ?? 0;
  const dailyNotionalUsed = dailyNotional?.notional_used ?? 0;

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <Skeleton className="h-80" />
      </div>
    );
  }

  return (
    <div className="space-y-10">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <KPICard
          label="Cash Available"
          value={formatCurrency(cryptoCash?.cash_available ?? accountOverview?.cash ?? 0)}
          subValue="Robinhood truth source"
          icon={DollarSign}
        />
        <KPICard
          label="Buying Power"
          value={formatCurrency(cryptoCash?.buying_power ?? accountOverview?.buying_power ?? 0)}
          subValue="Live crypto capacity"
          icon={TrendingUp}
        />
        <KPICard
          label="Realized P&L"
          value={formatCurrency(realizedPnl)}
          subValue={formatCurrency(todayPnl) + " daily change"}
          trend={
            todayPnl >= 0
              ? `+${formatPercentage(todayPnl / Math.max(equity || 1, 1))}`
              : formatPercentage(todayPnl / Math.max(equity || 1, 1))
          }
          trendDir={todayPnl >= 0 ? "up" : "down"}
          icon={DollarSign}
        />
        <KPICard
          label="Daily Notional Used"
          value={formatCurrency(dailyNotionalUsed)}
          subValue="Safety meter"
          icon={ShieldCheck}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-8">
          <EquityChart data={ef.pnlData} height={340} />

          <div className="card-premium p-8">
            <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-6">
              Crypto Holdings
            </h3>
            <div className="space-y-3">
              {holdingsRows.length > 0 ? (
                holdingsRows.map((holding) => (
                  <div
                    key={holding.asset}
                    className="grid grid-cols-3 text-xs items-center gap-4 bg-background/50 border border-border rounded-lg px-4 py-3"
                  >
                    <span className="font-black text-white">{holding.asset}</span>
                    <span className="font-mono text-text-secondary text-right">
                      {holding.qty.toFixed(8)}
                    </span>
                    <span className="font-mono text-right text-text-muted">
                      {holding.allocation.toFixed(1)}%
                    </span>
                  </div>
                ))
              ) : (
                <div className="text-text-dim text-xs italic">
                  No crypto holdings snapshot found yet.
                </div>
              )}
            </div>
          </div>

          <div className="card-premium p-8">
            <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-6">
              Trade Blotter
            </h3>
            <div className="space-y-2 max-h-[220px] overflow-y-auto">
              {cryptoOrders.length > 0 ? (
                cryptoOrders.map((order) => (
                  <div
                    key={order.id}
                    className="grid grid-cols-4 text-xs items-center gap-3 border-b border-border/40 py-2"
                  >
                    <span className="text-white font-bold">{order.symbol}</span>
                    <span className={order.side === "buy" ? "text-profit" : "text-loss"}>
                      {order.side.toUpperCase()}
                    </span>
                    <span className="text-text-secondary">
                      {formatCurrency(order.notional ?? 0)}
                    </span>
                    <span className="text-text-muted uppercase">{order.status}</span>
                  </div>
                ))
              ) : (
                <div className="text-text-dim text-xs italic">No crypto orders recorded.</div>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-8">
          <div className="card-premium p-6">
            <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-6 flex items-center gap-2">
              <Activity className="w-3 h-3 text-profit" /> Reconciliation Health
            </h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-text-secondary uppercase tracking-wider">
                  Status
                </span>
                <StatusChip
                  status={healthSummary.status === "LIVE" ? "ok" : "error"}
                  label={healthSummary.status}
                />
              </div>
              <div className="text-xs text-text-secondary">
                Last reconcile:{" "}
                {healthSummary.lastReconcile
                  ? new Date(healthSummary.lastReconcile).toLocaleString()
                  : "never"}
              </div>
              <div className="text-xs text-text-dim">Reason: {healthSummary.reason}</div>
              <div className="pt-4 mt-4 border-t border-border/50 text-[10px] font-bold text-text-dim flex justify-between uppercase tracking-widest">
                <span>Daily Notional</span>
                <span className="text-white">{formatCurrency(dailyNotionalUsed)}</span>
              </div>
            </div>
          </div>

          <div className="card-premium p-6">
            <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-6">
              System Integrity
            </h3>
            <div className="space-y-4">
              {healthStatus.length > 0 ? (
                healthStatus.map((h) => (
                  <div key={h.component} className="flex items-center justify-between">
                    <span className="text-xs font-bold text-text-secondary uppercase tracking-wider">
                      {h.component}
                    </span>
                    <StatusChip status={h.status} label={h.status.toUpperCase()} />
                  </div>
                ))
              ) : (
                <div className="text-text-dim text-xs italic py-2">
                  Establishing heartbeat sensor...
                </div>
              )}
            </div>
          </div>

          <div className="card-premium p-6">
            <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-6 flex items-center gap-2">
              <Zap className="w-3 h-3 text-warning" /> Edge Factory
            </h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-text-secondary uppercase tracking-wider">Regime</span>
                <span className={cn(
                  "text-[10px] font-black px-2 py-0.5 rounded-full uppercase tracking-wider",
                  ef.regime?.regime === "low_vol_bull" && "bg-profit/10 text-profit border border-profit/20",
                  ef.regime?.regime === "high_vol_crash" && "bg-loss/10 text-loss border border-loss/20",
                  ef.regime?.regime === "transition" && "bg-warning/10 text-warning border border-warning/20",
                  !ef.regime && "bg-white/5 text-text-muted border border-white/10"
                )}>
                  {ef.regime?.regime?.replace(/_/g, ' ') ?? 'Awaiting data'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-text-secondary uppercase tracking-wider">Open Positions</span>
                <span className="text-xs font-bold text-white">{ef.openPositions.length}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-text-secondary uppercase tracking-wider">Total P&L</span>
                <span className={cn(
                  "text-xs font-bold tabular-nums",
                  ef.totalPnl > 0 ? "text-profit" : ef.totalPnl < 0 ? "text-loss" : "text-text-muted"
                )}>
                  {ef.totalPnl >= 0 ? '+' : ''}{formatCurrency(ef.totalPnl)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-text-secondary uppercase tracking-wider">W / L</span>
                <span className="text-xs font-bold text-text-muted">
                  <span className="text-profit">{ef.wins}</span>
                  {' / '}
                  <span className="text-loss">{ef.losses}</span>
                </span>
              </div>
              {ef.closedPositions.length > 0 && (
                <div className="pt-3 mt-3 border-t border-border/50">
                  <div className="text-[10px] font-bold text-text-dim uppercase tracking-widest mb-2">Recent Trades</div>
                  <div className="space-y-1.5 max-h-[120px] overflow-y-auto">
                    {ef.closedPositions.slice(0, 5).map(pos => (
                      <div key={pos.id} className="flex items-center justify-between text-[10px]">
                        <span className="font-bold text-white">{pos.symbol}</span>
                        <span className={cn(
                          "font-bold tabular-nums",
                          (pos.pnl_usd ?? 0) >= 0 ? "text-profit" : "text-loss"
                        )}>
                          {(pos.pnl_usd ?? 0) >= 0 ? '+' : ''}{formatCurrency(pos.pnl_usd ?? 0)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="card-premium p-6">
            <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-6">
              Omniscient Feed
            </h3>
            <div className="space-y-6 max-h-[450px] overflow-y-auto pr-2 custom-scrollbar">
              {recentEvents.length > 0 ? (
                recentEvents.map((e, idx) => (
                  <div key={idx} className="flex gap-4 group">
                    <div
                      className={cn(
                        "w-1 h-12 rounded-full transition-all group-hover:w-1.5",
                        e.type === "TRADE" ? "bg-profit" : "bg-text-primary",
                      )}
                    />
                    <div>
                      <p className="text-xs text-text-primary leading-relaxed">
                        <span className="font-black text-white">{e.symbol}</span> {e.details}
                      </p>
                      <p className="text-[10px] font-bold text-text-dim mt-1 tabular-nums uppercase">
                        {new Date(e.event_ts).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit",
                          hour12: false,
                        })}
                      </p>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-text-dim text-xs italic">Awaiting first signal.</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
