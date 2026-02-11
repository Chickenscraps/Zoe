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
    <ShareLayout title="PORTFOLIO_SUMMARY">
      <div className="card-premium p-12 w-[1000px] flex flex-col gap-10 relative overflow-hidden">
        <div className="flex justify-between items-start relative z-10">
          <div className="flex items-center gap-8">
            <div className="w-20 h-20 bg-background border border-border rounded-2xl flex items-center justify-center shadow-crisp">
              <TrendingUp className="w-10 h-10 text-profit" />
            </div>
            <div>
              <h2 className="text-5xl font-black text-white tracking-tighter tabular-nums">
                {formatCurrency(stats.total_equity)}
              </h2>
              <p className="text-text-muted font-black tracking-[0.2em] uppercase text-xs mt-2">Net Equity</p>
            </div>
          </div>

          <div className="text-right">
            <div className="text-5xl font-black text-profit tracking-tighter tabular-nums">
              +{formatCurrency(stats.cumulative_pnl)}
            </div>
            <p className="text-text-dim font-black uppercase tracking-[0.2em] text-[10px] mt-2">Cumulative P&L</p>
          </div>
        </div>

        <div className="h-px bg-border/50 relative z-10" />

        <div className="grid grid-cols-3 gap-8 relative z-10">
          <div className="bg-background/50 border border-border rounded-2xl p-6">
            <div className="flex items-center gap-2 text-text-muted text-[10px] uppercase font-black tracking-[0.2em] mb-3">
              <Activity className="w-3.5 h-3.5 text-profit" /> Today
            </div>
            <div className="text-2xl font-black text-profit tabular-nums">+{formatCurrency(stats.today_pnl)}</div>
            <div className="text-xs text-text-muted mt-1">{formatPercentage(stats.today_return)}</div>
          </div>
          <div className="bg-background/50 border border-border rounded-2xl p-6">
            <div className="flex items-center gap-2 text-text-muted text-[10px] uppercase font-black tracking-[0.2em] mb-3">
              <TrendingUp className="w-3.5 h-3.5" /> Win Rate
            </div>
            <div className="text-2xl font-black text-white tabular-nums">{formatPercentage(stats.win_rate)}</div>
          </div>
          <div className="bg-background/50 border border-border rounded-2xl p-6">
            <div className="flex items-center gap-2 text-text-muted text-[10px] uppercase font-black tracking-[0.2em] mb-3">
              <Wallet className="w-3.5 h-3.5" /> PDT Usage
            </div>
            <div className="text-2xl font-black text-white tabular-nums">{stats.pdt_status}</div>
          </div>
        </div>
      </div>
    </ShareLayout>
  );
}
