import { DollarSign, TrendingUp } from "lucide-react";
import { EquityChart } from "../components/EquityChart";
import { KPICard } from "../components/KPICard";
import { Skeleton } from "../components/Skeleton";
import { useDashboardData } from "../hooks/useDashboardData";
import { formatCurrency, formatPercentage, cn } from "../lib/utils";

export default function Overview() {
  const {
    cryptoCash,
    livePrices,
    equityHistory,
    realizedPnl,
    loading,
  } = useDashboardData();

  // Use crypto cash snapshot as the source of truth
  const equity = cryptoCash?.buying_power ?? 0;
  const todayPnl = realizedPnl ?? 0;

  // Compute performance from equity history
  const startEquity = equityHistory.length > 0 ? equityHistory[0].equity : 0;
  const totalReturn = startEquity > 0 ? ((equity - startEquity) / startEquity) : 0;
  const totalReturnDollars = equity - startEquity;

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <Skeleton className="h-80" />
      </div>
    );
  }

  return (
    <div className="space-y-10">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <KPICard
          label="Net Equity"
          value={formatCurrency(equity)}
          subValue={formatCurrency(todayPnl) + " Daily Return"}
          trend={equity > 0 ? (todayPnl >= 0 ? "+"+formatPercentage(todayPnl/equity) : formatPercentage(todayPnl/equity)) : '0.00%'}
          trendDir={todayPnl >= 0 ? 'up' : 'down'}
          icon={DollarSign}
        />
        <KPICard
          label="Performance"
          value={startEquity > 0 ? (totalReturn >= 0 ? "+" : "") + formatPercentage(totalReturn) : "0.00%"}
          subValue={startEquity > 0 ? formatCurrency(totalReturnDollars) + " Total Return" : "Tracking from first snapshot"}
          trend={equityHistory.length > 1 ? `${equityHistory.length}d tracked` : "Warming up"}
          trendDir={totalReturn >= 0 ? 'up' : 'down'}
          icon={TrendingUp}
        />
        <KPICard
          label="Settled Cash"
          value={formatCurrency(equity)}
          subValue="T+1 Settlement"
          trend="Ready"
          trendDir="up"
          icon={DollarSign}
        />
      </div>

      {/* Live Crypto Prices */}
      {livePrices.length > 0 && (
        <div className="card-premium p-6">
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted flex items-center gap-2">
              <TrendingUp className="w-3 h-3 text-profit" /> Live Prices
            </h3>
            <span className="text-[9px] font-bold text-text-dim uppercase tracking-widest">
              {livePrices[0]?.created_at ? new Date(livePrices[0].created_at).toLocaleTimeString([], { hour12: false }) : ''}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
            {livePrices.slice(0, 10).map((scan) => {
              const info = scan.info as any ?? {};
              const mid = info.mid ?? 0;
              const momShort = info.momentum_short;
              const isUp = momShort != null ? momShort >= 0 : true;
              return (
                <div key={scan.symbol} className="flex flex-col items-center p-3 bg-background/50 border border-border rounded-xl hover:border-white/10 transition-colors">
                  <span className="text-[10px] font-black text-text-muted uppercase tracking-widest mb-1">
                    {scan.symbol.replace('-USD', '')}
                  </span>
                  <span className="text-sm font-bold text-white tabular-nums">
                    {mid >= 1 ? `$${mid.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : `$${mid.toFixed(6)}`}
                  </span>
                  {momShort != null && (
                    <span className={cn(
                      "text-[10px] font-bold tabular-nums mt-0.5",
                      isUp ? "text-profit" : "text-loss"
                    )}>
                      {isUp ? '▲' : '▼'} {Math.abs(momShort).toFixed(3)}%
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="space-y-8">
        <EquityChart data={equityHistory} height={400} />

        <div className="card-premium p-8">
           <h3 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted mb-6">Account Architecture</h3>
           <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
              <div className="p-6 bg-background/50 border border-border rounded-xl">
                <p className="text-[10px] uppercase font-medium tracking-widest text-text-dim mb-2">Buying Power</p>
                <p className="text-xl font-semibold text-white tabular-nums">{formatCurrency(equity)}</p>
              </div>
              <div className="p-6 bg-background/50 border border-border rounded-xl">
                <p className="text-[10px] uppercase font-medium tracking-widest text-text-dim mb-2">Settled Balance</p>
                <p className="text-xl font-semibold text-white tabular-nums">{formatCurrency(equity)}</p>
              </div>
              <div className="p-6 bg-background/50 border border-border rounded-xl">
                <p className="text-[10px] uppercase font-medium tracking-widest text-text-dim mb-2">Sync Status</p>
                <p className="text-xs font-mono font-medium text-text-muted uppercase tracking-tighter mt-1">
                  {cryptoCash?.taken_at ? new Date(cryptoCash.taken_at).toLocaleTimeString([], { hour12: false }) : 'DISCONNECTED'}
                </p>
              </div>
           </div>
        </div>
      </div>
    </div>
  );
}
