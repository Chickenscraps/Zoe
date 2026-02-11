import { Activity, DollarSign, TrendingUp, ShieldCheck, ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";
import { EquityChart } from "../components/EquityChart";
import { KPICard } from "../components/KPICard";
import { Skeleton } from "../components/Skeleton";
import { StatusChip } from "../components/StatusChip";
import { useDashboardData } from "../hooks/useDashboardData";
import { formatCurrency, formatPercentage, cn } from "../lib/utils";

export default function Overview() {
  const {
    accountOverview,
    recentEvents,
    healthStatus,
    cryptoCash,
    holdingsRows,
    healthSummary,
    dailyNotional,
    pnlDaily,
    realizedPnl,
    cryptoOrders,
    livePrices,
    loading,
    error,
  } = useDashboardData();

  const equity = accountOverview?.equity ?? 0;
  const todayPnl = accountOverview?.day_pnl ?? 0;
  const dailyNotionalUsed = dailyNotional?.amount ?? 0;

  const currentEquity = (cryptoCash?.buying_power ?? equity) || 2000;
  const displayPnl = pnlDaily.length > 0
    ? pnlDaily
    : (() => {
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        return [
          { date: yesterday.toISOString().slice(0, 10), equity: currentEquity, daily_pnl: 0 },
          { date: today.toISOString().slice(0, 10), equity: currentEquity, daily_pnl: 0 },
        ];
      })();

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

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 space-y-4">
        <div className="text-loss text-sm font-bold uppercase tracking-widest">Connection Error</div>
        <p className="text-text-secondary text-sm max-w-md text-center">
          Failed to load dashboard data. Check that Supabase environment variables are configured.
        </p>
        <code className="text-xs text-text-dim bg-surface-base border border-border rounded-lg px-4 py-2 max-w-lg overflow-auto">
          {error}
        </code>
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

      {/* Live Prices Ticker */}
      {livePrices.length > 0 && (
        <div className="card-premium p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted">
              Live Prices
            </h3>
            <span className="text-[9px] text-text-dim font-bold uppercase tracking-widest">
              {livePrices[0]?.created_at
                ? new Date(livePrices[0].created_at).toLocaleTimeString()
                : ""}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
            {livePrices.map((scan) => {
              const info = scan.info as any ?? {};
              const mid = info.mid ?? 0;
              const momShort = info.momentum_short;
              const rsi = info.rsi;
              const isUp = momShort != null && momShort > 0;
              const isDown = momShort != null && momShort < 0;
              const symbol = (scan.symbol ?? "").replace("-USD", "");

              return (
                <div
                  key={scan.id}
                  className="bg-background/60 border border-border/50 rounded-xl px-4 py-3 flex flex-col gap-1 hover:border-border transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-black text-white tracking-tight">{symbol}</span>
                    {isUp ? (
                      <ArrowUpRight className="w-3.5 h-3.5 text-profit" />
                    ) : isDown ? (
                      <ArrowDownRight className="w-3.5 h-3.5 text-loss" />
                    ) : (
                      <Minus className="w-3 h-3 text-text-dim" />
                    )}
                  </div>
                  <div className="text-sm font-black text-white tabular-nums tracking-tight">
                    {mid >= 1
                      ? `$${mid.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                      : `$${mid.toFixed(6)}`}
                  </div>
                  <div className="flex items-center gap-2">
                    {momShort != null && (
                      <span
                        className={cn(
                          "text-[10px] font-bold tabular-nums",
                          isUp ? "text-profit" : isDown ? "text-loss" : "text-text-dim"
                        )}
                      >
                        {momShort > 0 ? "+" : ""}
                        {momShort.toFixed(3)}%
                      </span>
                    )}
                    {rsi != null && (
                      <span
                        className={cn(
                          "text-[9px] font-bold tabular-nums",
                          rsi > 70 ? "text-orange-400" : rsi < 30 ? "text-blue-400" : "text-text-dim"
                        )}
                      >
                        RSI {rsi.toFixed(0)}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-8">
          <EquityChart data={displayPnl} height={340} />

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
