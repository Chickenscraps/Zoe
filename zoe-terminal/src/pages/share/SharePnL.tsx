import { ShareLayout } from '../../components/ShareLayout';
import { formatCurrency } from '../../lib/utils';
import { TrendingUp, Activity, Wallet } from 'lucide-react';

export default function SharePnL() {
  const stats = {
    total_equity: 150.00,
    cumulative_pnl: 0.00,
    today_pnl: 0.00,
    today_return: 0,
    win_rate: 0,
    trades: 0,
  };

  const pnlColor = stats.cumulative_pnl >= 0 ? 'text-profit' : 'text-loss';

  return (
    <ShareLayout title="P&L_SUMMARY">
      <div className="w-full max-w-[900px] card-premium p-12 space-y-8">
        <div className="grid grid-cols-3 gap-8">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-[10px] font-black text-text-muted uppercase tracking-[0.15em]">
              <Wallet className="w-3 h-3" /> Total Equity
            </div>
            <div className="text-4xl font-black text-white tabular-nums tracking-tight">
              {formatCurrency(stats.total_equity)}
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-[10px] font-black text-text-muted uppercase tracking-[0.15em]">
              <TrendingUp className="w-3 h-3" /> Cumulative P&L
            </div>
            <div className={`text-4xl font-black tabular-nums tracking-tight ${pnlColor}`}>
              {stats.cumulative_pnl >= 0 ? '+' : ''}{formatCurrency(stats.cumulative_pnl)}
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-[10px] font-black text-text-muted uppercase tracking-[0.15em]">
              <Activity className="w-3 h-3" /> Win Rate
            </div>
            <div className="text-4xl font-black text-white tabular-nums tracking-tight">
              {stats.trades > 0 ? `${(stats.win_rate * 100).toFixed(0)}%` : '--'}
            </div>
          </div>
        </div>

        <div className="border-t border-border/50 pt-6">
          <div className="flex items-center justify-between text-xs">
            <span className="text-text-muted font-bold uppercase tracking-wider">Today</span>
            <span className={`font-bold tabular-nums ${stats.today_pnl >= 0 ? 'text-profit' : 'text-loss'}`}>
              {stats.today_pnl >= 0 ? '+' : ''}{formatCurrency(stats.today_pnl)}
            </span>
          </div>
          <div className="flex items-center justify-between text-xs mt-2">
            <span className="text-text-muted font-bold uppercase tracking-wider">Total Trades</span>
            <span className="font-bold text-white">{stats.trades}</span>
          </div>
        </div>

        {stats.trades === 0 && (
          <div className="text-center py-4">
            <p className="text-xs text-text-muted">Edge Factory awaiting first trade</p>
          </div>
        )}
      </div>
    </ShareLayout>
  );
}
