import { ShareLayout } from '../../components/ShareLayout';
import { formatCurrency, formatPercentage } from '../../lib/utils';
import { TrendingUp, Activity, BarChart3, Wallet } from 'lucide-react';

export default function SharePnL() {
  // Mock data for the summary
  const stats = {
    total_equity: 12450.60,
    cumulative_pnl: 2450.60,
    today_pnl: 142.30,
    today_return: 0.012,
    win_rate: 0.68,
    pdt_status: '2 / 3'
  };

  return (
    <ShareLayout title="PERFORMANCE_SNAPSHOT">
      <div 
        data-testid="pnl-summary"
        className="bg-surface/80 backdrop-blur-md border border-white/10 rounded-2xl shadow-2xl p-8 w-[900px] flex flex-col gap-8"
      >
        {/* Large Stats */}
        <div className="grid grid-cols-2 gap-8">
          <div>
            <div className="flex items-center gap-2 text-text-muted text-xs uppercase font-bold tracking-widest mb-2">
              <Wallet className="w-4 h-4" /> Total Equity
            </div>
            <div className="text-6xl font-black text-white tracking-tighter">
              {formatCurrency(stats.total_equity)}
            </div>
          </div>
          <div className="text-right">
            <div className="flex items-center gap-2 justify-end text-text-muted text-xs uppercase font-bold tracking-widest mb-2">
              <TrendingUp className="w-4 h-4" /> Cumulative P&L
            </div>
            <div className="text-6xl font-black text-profit tracking-tighter">
              +{formatCurrency(stats.cumulative_pnl)}
            </div>
          </div>
        </div>

        <div className="h-px bg-white/5" />

        {/* Breakdown Grid */}
        <div className="grid grid-cols-3 gap-6">
          <div className="bg-white/5 rounded-2xl p-6 border border-white/5 flex flex-col gap-2">
            <div className="text-text-muted text-xs uppercase font-bold tracking-widest">Today's P&L</div>
            <div className="text-3xl font-black text-profit">
              {formatCurrency(stats.today_pnl)}
            </div>
            <div className="text-sm font-mono text-profit">
              ({formatPercentage(stats.today_return)})
            </div>
          </div>

          <div className="bg-white/5 rounded-2xl p-6 border border-white/5 flex flex-col gap-2">
            <div className="text-text-muted text-xs uppercase font-bold tracking-widest">Win Rate</div>
            <div className="text-3xl font-black text-white">
              {formatPercentage(stats.win_rate)}
            </div>
            <div className="flex items-center gap-2 mt-1">
              <div className="flex-1 h-1 bg-white/10 rounded-full overflow-hidden">
                <div className="h-full bg-brand" style={{ width: `${stats.win_rate * 100}%` }} />
              </div>
            </div>
          </div>

          <div className="bg-white/5 rounded-2xl p-6 border border-white/5 flex flex-col gap-2">
            <div className="text-text-muted text-xs uppercase font-bold tracking-widest">PDT Usage</div>
            <div className="text-3xl font-black text-white">
              {stats.pdt_status}
            </div>
            <div className="text-xs text-text-muted font-mono tracking-widest">
              RESET_IN_2D
            </div>
          </div>
        </div>

        {/* Sparkline Placeholder / Aesthetic Graph */}
        <div className="mt-4 bg-black/20 rounded-2xl p-6 border border-white/5 relative h-32 flex items-end gap-2 overflow-hidden">
          <div className="absolute top-4 left-6 flex items-center gap-2 text-[10px] text-text-muted uppercase font-bold tracking-widest">
            <Activity className="w-3 h-3" /> Historical Trend
          </div>
          {/* Aesthetic Bars */}
          {[40, 60, 45, 70, 85, 60, 55, 90, 80, 100, 95, 110, 130, 120, 140, 160].map((h, i) => (
            <div 
              key={i} 
              className="flex-1 bg-brand/20 rounded-t-sm" 
              style={{ height: `${(h / 160) * 100}%` }} 
            />
          ))}
          <div className="absolute inset-x-0 bottom-0 h-1 bg-brand shadow-[0_0_20px_rgba(var(--brand-rgb),0.5)]" />
        </div>
      </div>
    </ShareLayout>
  );
}
