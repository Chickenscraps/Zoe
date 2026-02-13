import { Activity, DollarSign, TrendingUp } from "lucide-react";
import { EquityChart } from "../components/EquityChart";
import { KPICard } from "../components/KPICard";
import { Skeleton } from "../components/Skeleton";
import { StatusChip } from "../components/StatusChip";
import { useDashboardData } from "../hooks/useDashboardData";
import { formatCurrency, formatPercentage, cn } from "../lib/utils";

export default function Overview() {
  const {
    recentEvents,
    healthStatus,
    cryptoCash,
    holdingsRows,
    healthSummary,
    dailyNotional,
    realizedPnl,
    cryptoOrders,
    livePrices,
    equityHistory,
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
    <div className="space-y-6 sm:space-y-10">
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 sm:gap-6">
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
        <div className="card-premium p-4 sm:p-6">
          <div className="flex items-center justify-between mb-4 sm:mb-5">
            <h3 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted flex items-center gap-2">
              <TrendingUp className="w-3 h-3 text-profit" /> Live Prices
            </h3>
            <span className="text-[9px] font-bold text-text-dim uppercase tracking-widest">
              {livePrices[0]?.created_at ? new Date(livePrices[0].created_at).toLocaleTimeString([], { hour12: false }) : ''}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2 sm:gap-4">
            {livePrices.slice(0, 10).map((scan) => {
              const info = scan.info as any ?? {};
              const mid = info.mid ?? 0;
              const momShort = info.momentum_short;
              const isUp = momShort != null ? momShort >= 0 : true;
              return (
                <div key={scan.symbol} className="flex flex-col items-center p-2 sm:p-3 bg-background/50 border border-border rounded-xl hover:border-white/10 transition-colors">
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8">
        <div className="lg:col-span-2 space-y-6 sm:space-y-8">
          <EquityChart data={equityHistory} height={window.innerWidth < 640 ? 250 : 400} />

          <div className="card-premium p-4 sm:p-8">
             <h3 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted mb-4 sm:mb-6">Account Architecture</h3>
             <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-6 text-center">
                <div className="p-4 sm:p-6 bg-background/50 border border-border rounded-xl">
                  <p className="text-[10px] uppercase font-medium tracking-widest text-text-dim mb-1 sm:mb-2">Buying Power</p>
                  <p className="text-lg sm:text-xl font-semibold text-white tabular-nums">{formatCurrency(equity)}</p>
                </div>
                <div className="p-4 sm:p-6 bg-background/50 border border-border rounded-xl">
                  <p className="text-[10px] uppercase font-medium tracking-widest text-text-dim mb-1 sm:mb-2">Settled Balance</p>
                  <p className="text-lg sm:text-xl font-semibold text-white tabular-nums">{formatCurrency(equity)}</p>
                </div>
                <div className="p-4 sm:p-6 bg-background/50 border border-border rounded-xl">
                  <p className="text-[10px] uppercase font-medium tracking-widest text-text-dim mb-1 sm:mb-2">Sync Status</p>
                  <p className="text-xs font-mono font-medium text-text-muted uppercase tracking-tighter mt-1">
                    {cryptoCash?.taken_at ? new Date(cryptoCash.taken_at).toLocaleTimeString([], { hour12: false }) : 'DISCONNECTED'}
                  </p>
                </div>
             </div>
          </div>
        </div>

        <div className="space-y-8">
           {/* System Health */}
           <div className="card-premium p-6">
             <h3 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted mb-6 flex items-center gap-2">
               <Activity className="w-3 h-3 text-profit" /> System Integrity
             </h3>
             <div className="space-y-4">
               {healthStatus.length > 0 ? healthStatus.map(h => (
                 <div key={h.component} className="flex items-center justify-between">
                   <span className="text-xs font-medium text-text-secondary uppercase tracking-wider">{h.component}</span>
                   <StatusChip status={h.status} label={h.status.toUpperCase()} />
                 </div>
               )) : (
                 <div className="text-text-dim text-xs italic py-2">Establishing heartbeat sensor...</div>
               )}
               <div className="pt-4 mt-4 border-t border-border/50 text-[10px] font-medium text-text-dim flex justify-between uppercase tracking-widest">
                 <span>Instance ID</span>
                 <span className="text-white">PRM-V4-AUTONOMOUS</span>
               </div>
             </div>
           </div>

           {/* Activity Feed */}
           <div className="card-premium p-6">
             <h3 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted mb-6">Omniscient Feed</h3>
             <div className="space-y-6 max-h-[300px] sm:max-h-[450px] overflow-y-auto pr-2 scroll-smooth-mobile">
               {recentEvents.length > 0 ? recentEvents.map((e, idx) => (
                 <div key={idx} className="flex gap-4 group min-w-0">
                   <div className={cn(
                     "w-1 h-12 rounded-full transition-all group-hover:w-1.5",
                     e.type === 'TRADE' ? 'bg-profit' : 'bg-text-primary'
                   )} />
                   <div>
                     <p className="text-xs text-text-primary leading-relaxed">
                        <span className="font-semibold text-white">{e.symbol}</span> {e.details}
                     </p>
                     <p className="text-[10px] font-medium text-text-dim mt-1 tabular-nums uppercase">
                        {new Date(e.event_ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}
                     </p>
                   </div>
                 </div>
               )) : (
                 <div className="text-text-dim text-xs italic">Awaiting first signal.</div>
               )}
             </div>
           </div>
        </div>
      </div>
    </div>
  );
}
