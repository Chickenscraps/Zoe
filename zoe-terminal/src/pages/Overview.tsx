import { useDashboardData } from '../hooks/useDashboardData';
import { KPICard } from '../components/KPICard';
import { EquityChart } from '../components/EquityChart';
import { StatusChip } from '../components/StatusChip';
import { Skeleton } from '../components/Skeleton';
import { Activity, DollarSign, TrendingUp, AlertTriangle, ShieldCheck } from 'lucide-react';
import { formatCurrency, formatPercentage, formatDate } from '../lib/utils';

export default function Overview() {
  const { pnlHistory, recentEvents, healthStatus, loading } = useDashboardData();

  // Derived stats
  const today = pnlHistory.length > 0 ? pnlHistory[pnlHistory.length - 1] : null;

  const todayPnl = today?.daily_pnl ?? 0;
  const winRate = today?.win_rate ?? 0;
  
  // Mock fallback if empty (for demo purposes)
  const displayPnl = pnlHistory.length ? pnlHistory : [
     { date: '2023-10-01', equity: 10000 },
     { date: '2023-10-02', equity: 10200 },
     { date: '2023-10-03', equity: 10150 },
     { date: '2023-10-04', equity: 10400 },
     { date: '2023-10-05', equity: 10800 },
  ].map(d => ({ ...d, instance_id: 'demo', daily_pnl: 0, drawdown: 0, win_rate: 0, expectancy: 0, cash_buffer_pct: 0, day_trades_used: 0, realized_pnl: 0, unrealized_pnl: 0 }));

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
          value={formatCurrency(today?.equity ?? 2000)} 
          subValue={formatCurrency(today?.daily_pnl ?? 0) + " Today"}
          trend={todayPnl >= 0 ? "+"+formatPercentage(todayPnl/2000) : formatPercentage(todayPnl/2000)}
          trendDir={todayPnl >= 0 ? 'up' : 'down'}
          icon={DollarSign}
        />
        <KPICard 
          label="Win Rate" 
          value={formatPercentage(winRate * 100, 0)} 
          subValue="Last 20 trades"
          trend="Stable"
          trendDir="neutral"
          icon={TrendingUp}
        />
        <KPICard 
          label="Drawdown" 
          value={formatPercentage((today?.drawdown ?? 0), 2)} 
          trend="Within Limits"
          trendDir="up" // Up is good for "within limits" context? Or keep neutral
          icon={AlertTriangle}
        />
         <KPICard 
          label="Day Trades" 
          value={`${today?.day_trades_used ?? 0} / 3`} 
          subValue="PDT Budget"
          icon={ShieldCheck}
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Equity Chart (2 cols) */}
        <div className="lg:col-span-2 space-y-6">
          <EquityChart data={displayPnl} height={350} />
          
          <div className="bg-surface border border-border rounded-lg p-4">
             <h3 className="text-sm font-medium text-text-secondary mb-4">Paper Performance</h3>
             {/* Placeholder for more stats or drawdown chart */}
             <div className="h-40 flex items-center justify-center text-text-muted text-sm border border-dashed border-border rounded">
               Drawdown Chart Placeholder
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
                 <>
                   <div className="flex items-center justify-between text-sm">
                     <span>Data Provider</span>
                     <StatusChip status="ok" label="ONLINE" />
                   </div>
                   <div className="flex items-center justify-between text-sm">
                     <span>Trading Engine</span>
                     <StatusChip status="ok" label="ONLINE" />
                   </div>
                   <div className="flex items-center justify-between text-sm">
                     <span>Supabase</span>
                     <StatusChip status="ok" label="ONLINE" />
                   </div>
                 </>
               )}
               <div className="pt-2 mt-2 border-t border-border text-xs text-text-muted flex justify-between">
                 <span>Last Heartbeat</span>
                 <span>{new Date().toLocaleTimeString()}</span>
               </div>
             </div>
           </div>

           {/* Recent Events */}
           <div className="bg-surface border border-border rounded-lg p-4">
             <h3 className="text-sm font-medium text-text-secondary mb-4">Latest Events</h3>
             <div className="space-y-4">
               {recentEvents.length > 0 ? recentEvents.map(e => (
                 <div key={e.id} className="flex gap-3 text-sm">
                   <div className="w-1 h-full bg-border rounded-full" />
                   <div>
                     <p className="text-text-primary">{e.message}</p>
                     <p className="text-xs text-text-muted">{formatDate(e.created_at)}</p>
                   </div>
                 </div>
               )) : (
                 <div className="text-text-muted text-sm italic">No recent events</div>
               )}
             </div>
           </div>
        </div>
      </div>
    </div>
  );
}
