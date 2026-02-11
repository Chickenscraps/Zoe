import { ShareLayout } from '../../components/ShareLayout';
import { formatCurrency, formatPercentage } from '../../lib/utils';
import { TrendingUp, Activity, Wallet } from 'lucide-react';

export default function SharePnL() {
  const stats = {
    total_equity: 12450.60,
    cumulative_pnl: 2450.60,
    today_pnl: 142.30,
    today_return: 0.012,
    win_rate: 0.68,
    pdt_status: '2 / 3'
  };

  return (
    <ShareLayout title="SESSION_PNL_REPORT">
      <div data-testid="pnl-ticket" className="card-premium p-12 w-[1100px] flex flex-col gap-10 relative overflow-hidden">
        <div className="flex justify-between items-end pb-8 border-b border-border/50">
          <div>
            <div className="text-profit font-black text-[10px] uppercase tracking-[0.3em] mb-3">Performance Layer</div>
            <h1 className="text-5xl font-black text-white tracking-tighter uppercase">Session Summary</h1>
          </div>
          <div className="text-right">
            <div className="text-text-muted font-black text-[10px] uppercase tracking-[0.3em] mb-3">Report Date</div>
            <div className="text-2xl text-white font-black tracking-tight tabular-nums">
              {new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).toUpperCase()}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-8">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-[10px] font-black text-text-muted uppercase tracking-[0.2em]">
              <Wallet className="w-3 h-3 text-profit" /> Total Equity
            </div>
            <div className="text-3xl font-black text-white tracking-tighter tabular-nums">{formatCurrency(stats.total_equity)}</div>
          </div>
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-[10px] font-black text-text-muted uppercase tracking-[0.2em]">
              <TrendingUp className="w-3 h-3 text-profit" /> Today P&L
            </div>
            <div className="text-3xl font-black text-profit tracking-tighter tabular-nums">{formatCurrency(stats.today_pnl)}</div>
          </div>
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-[10px] font-black text-text-muted uppercase tracking-[0.2em]">
              <Activity className="w-3 h-3" /> Win Rate
            </div>
            <div className="text-3xl font-black text-white tracking-tighter tabular-nums">{formatPercentage(stats.win_rate)}</div>
          </div>
        </div>
      </div>
    </ShareLayout>
  );
}
