import { Activity, DollarSign, TrendingUp, ShieldCheck } from "lucide-react";
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
    realizedPnl,
    cryptoOrders,
    loading,
  } = useDashboardData();

  // Stats from RPC — no fallbacks to fake data
  const equity = accountOverview?.equity ?? 0;
  const todayPnl = accountOverview?.day_pnl ?? 0;
  const pdtCount = accountOverview?.pdt_count ?? 0;

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
          label="Net Equity"
          value={formatCurrency(equity)}
          subValue={formatCurrency(todayPnl) + " Daily Return"}
          trend={equity > 0 ? (todayPnl >= 0 ? "+"+formatPercentage(todayPnl/equity) : formatPercentage(todayPnl/equity)) : '--'}
          trendDir={todayPnl >= 0 ? 'up' : 'down'}
          icon={DollarSign}
        />
        <KPICard
          label="Performance"
          value="--"
          subValue="Real-time Alpha"
          trend="Static"
          trendDir="neutral"
          icon={TrendingUp}
        />
        <KPICard
          label="Settled Cash"
          value={formatCurrency(accountOverview?.cash ?? 0)}
          subValue="T+1 Settlement"
          trend="Ready"
          trendDir="up"
          icon={DollarSign}
        />
         <KPICard
          label="Day Trade Load"
          value={`${pdtCount} / 3`}
          subValue="PDT Protocol active"
          icon={ShieldCheck}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-8">
          <EquityChart data={[]} height={400} />

          <div className="card-premium p-8">
             <h3 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted mb-6">Account Architecture</h3>
             <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
                <div className="p-6 bg-background/50 border border-border rounded-xl">
                  <p className="text-[10px] uppercase font-medium tracking-widest text-text-dim mb-2">Buying Power</p>
                  <p className="text-xl font-semibold text-white tabular-nums">{formatCurrency(accountOverview?.buying_power ?? 0)}</p>
                </div>
                <div className="p-6 bg-background/50 border border-border rounded-xl">
                  <p className="text-[10px] uppercase font-medium tracking-widest text-text-dim mb-2">Settled Balance</p>
                  <p className="text-xl font-semibold text-white tabular-nums">{formatCurrency(accountOverview?.cash ?? 0)}</p>
                </div>
                <div className="p-6 bg-background/50 border border-border rounded-xl">
                  <p className="text-[10px] uppercase font-medium tracking-widest text-text-dim mb-2">Sync Status</p>
                  <p className="text-xs font-mono font-medium text-text-muted uppercase tracking-tighter mt-1">
                    {accountOverview?.last_updated ? new Date(accountOverview.last_updated).toLocaleTimeString([], { hour12: false }) : 'DISCONNECTED'}
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

           {/* Activity Feed (From RPC) */}
           <div className="card-premium p-6">
             <h3 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted mb-6">Omniscient Feed</h3>
             <div className="space-y-6 max-h-[450px] overflow-y-auto pr-2 custom-scrollbar">
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
