import { useDashboardData } from '../hooks/useDashboardData';
import { KPICard } from '../components/KPICard';
import { EquityChart } from '../components/EquityChart';
import { StatusChip } from '../components/StatusChip';
import { Skeleton } from '../components/Skeleton';
import { Activity, DollarSign, TrendingUp, ShieldCheck } from 'lucide-react';
import { formatCurrency, formatPercentage } from '../lib/utils';

export default function Overview() {
  const { accountOverview, recentEvents, healthStatus, loading } = useDashboardData();

  // Stats from RPC
  const equity = accountOverview?.equity ?? 2000;
  const todayPnl = accountOverview?.day_pnl ?? 0;
  const pdtCount = accountOverview?.pdt_count ?? 0;
  
  // Mock fallback for chart until we have pnl_history RPC
  const displayPnl = [
     { date: '2023-10-01', equity: 10000 },
     { date: '2023-10-02', equity: 10200 },
     { date: '2023-10-03', equity: 10150 },
     { date: '2023-10-04', equity: 10400 },
     { date: '2023-10-05', equity: 10800 },
  ].map(d => ({ ...d, daily_pnl: 0 }));

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
           {[1,2,3,4].map(i => <Skeleton key={i} className="h-32" />)}
        </div>
        <Skeleton className="h-80" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard 
          label="Total Equity" 
          value={formatCurrency(equity)} 
          subValue={formatCurrency(todayPnl) + " Today"}
          trend={todayPnl >= 0 ? "+"+formatPercentage(todayPnl/equity) : formatPercentage(todayPnl/equity)}
          trendDir={todayPnl >= 0 ? 'up' : 'down'}
          icon={DollarSign}
        />
        <KPICard 
          label="Win Rate" 
          value="--" 
          subValue="Calculated in Engine"
          trend="Stable"
          trendDir="neutral"
          icon={TrendingUp}
        />
        <KPICard 
          label="Cash" 
          value={formatCurrency(accountOverview?.cash ?? 0)} 
          trend="Available"
          trendDir="up"
          icon={DollarSign}
        />
         <KPICard 
          label="Day Trades" 
          value={`${pdtCount} / 3`} 
          subValue="PDT History"
          icon={ShieldCheck}
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Equity Chart (2 cols) */}
        <div className="lg:col-span-2 space-y-6">
          <EquityChart data={displayPnl} height={350} />
          
          <div className="bg-surface border border-border rounded-lg p-4">
             <h3 className="text-sm font-medium text-text-secondary mb-4">Account Snapshot</h3>
             <div className="grid grid-cols-3 gap-4 text-center">
                <div className="p-4 bg-background border border-border rounded-lg">
                  <p className="text-xs text-text-muted mb-1">Buying Power</p>
                  <p className="text-lg font-bold text-text-primary">{formatCurrency(accountOverview?.buying_power ?? 0)}</p>
                </div>
                <div className="p-4 bg-background border border-border rounded-lg">
                  <p className="text-xs text-text-muted mb-1">Cash Balance</p>
                  <p className="text-lg font-bold text-text-primary">{formatCurrency(accountOverview?.cash ?? 0)}</p>
                </div>
                <div className="p-4 bg-background border border-border rounded-lg">
                  <p className="text-xs text-text-muted mb-1">Last Update</p>
                  <p className="text-sm font-medium text-text-secondary">{accountOverview?.last_updated ? new Date(accountOverview.last_updated).toLocaleTimeString() : '--'}</p>
                </div>
             </div>
          </div>
        </div>

        {/* Sidebar Widgets (1 col) */}
        <div className="space-y-6">
           {/* System Health */}
           <div className="bg-surface border border-border rounded-lg p-4">
             <h3 className="text-sm font-medium text-text-secondary mb-4 flex items-center gap-2">
               <Activity className="w-4 h-4" /> System Health
             </h3>
             <div className="space-y-3">
               {healthStatus.length > 0 ? healthStatus.map(h => (
                 <div key={h.component} className="flex items-center justify-between text-sm">
                   <span className="capitalize">{h.component}</span>
                   <StatusChip status={h.status} label={h.status.toUpperCase()} />
                 </div>
               )) : (
                 <div className="text-text-muted text-sm italic py-2">Waiting for heartbeats...</div>
               )}
               <div className="pt-2 mt-2 border-t border-border text-xs text-text-muted flex justify-between">
                 <span>Reference Node</span>
                 <span>Primary-V4</span>
               </div>
             </div>
           </div>

           {/* Activity Feed (From RPC) */}
           <div className="bg-surface border border-border rounded-lg p-4">
             <h3 className="text-sm font-medium text-text-secondary mb-4">Live Activity</h3>
             <div className="space-y-4 max-h-[400px] overflow-y-auto pr-2">
               {recentEvents.length > 0 ? recentEvents.map((e, idx) => (
                 <div key={idx} className="flex gap-3 text-sm">
                   <div className={`w-1 h-8 rounded-full ${e.type === 'TRADE' ? 'bg-profit' : 'bg-brand'}`} />
                   <div>
                     <p className="text-text-primary"><span className="font-bold">{e.symbol}</span>: {e.details}</p>
                     <p className="text-xs text-text-muted">{new Date(e.event_ts).toLocaleTimeString()}</p>
                   </div>
                 </div>
               )) : (
                 <div className="text-text-muted text-sm italic">No activity recorded</div>
               )}
             </div>
           </div>
        </div>
      </div>
    </div>
  );
}
