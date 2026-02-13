import { useEffect, useState } from 'react';
import { ShareLayout } from '../../components/ShareLayout';
import { formatCurrency, formatPercentage } from '../../lib/utils';
import { TrendingUp, Activity, Wallet } from 'lucide-react';
import { supabase } from '../../lib/supabaseClient';

interface PnlStats {
  total_equity: number;
  cumulative_pnl: number;
  today_pnl: number;
  today_return: number;
  win_rate: number;
  pdt_status: string;
}

export default function SharePnL() {
  const [stats, setStats] = useState<PnlStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchStats() {
      try {
        const { data, error } = await supabase
          .rpc('get_account_overview' as any, { p_discord_id: '292890243852664855' } as any);

        if (error) throw error;
        const rows = data as any;
        if (rows && Array.isArray(rows) && rows.length > 0) {
          const d = rows[0];
          setStats({
            total_equity: d.equity ?? 0,
            cumulative_pnl: d.cumulative_pnl ?? d.day_pnl ?? 0,
            today_pnl: d.day_pnl ?? 0,
            today_return: d.equity ? (d.day_pnl ?? 0) / d.equity : 0,
            win_rate: d.win_rate ?? 0,
            pdt_status: `${d.pdt_count ?? 0} / 3`,
          });
        }
      } catch (err) {
        console.error('Error fetching PnL stats:', err);
      } finally {
        setLoading(false);
      }
    }
    fetchStats();
  }, []);

  if (loading) return <div className="p-8 text-earth-700">Loading P&L...</div>;
  if (!stats) return <div className="p-8 text-earth-700">No P&L data available</div>;

  const pnlPositive = stats.cumulative_pnl >= 0;

  return (
    <ShareLayout title="PNL_SUMMARY">
      <div className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] p-12 w-[1000px] flex flex-col gap-10 relative overflow-hidden">
        {/* Header */}
        <div className="flex justify-between items-start relative z-10">
          <div className="flex items-center gap-8">
            <div className="w-20 h-20 bg-cream-100 border-2 border-earth-700/10 rounded-[4px] flex items-center justify-center">
              <TrendingUp className="w-10 h-10 text-sakura-700" />
            </div>
            <div>
              <h2 className="text-5xl font-bold text-earth-700 tracking-tighter">Portfolio P&L</h2>
              <p className="text-text-muted font-semibold tracking-[0.2em] uppercase text-xs mt-2">Autonomous Session Report</p>
            </div>
          </div>

          <div className="text-right">
            <div className={`text-5xl font-bold tracking-tighter tabular-nums ${pnlPositive ? 'text-profit' : 'text-loss'}`}>
              {pnlPositive ? '+' : ''}{formatCurrency(stats.cumulative_pnl)}
            </div>
            <p className="text-text-dim font-semibold uppercase tracking-[0.2em] text-[10px] mt-2">Cumulative Net Yield</p>
          </div>
        </div>

        <div className="h-px bg-earth-700/10 relative z-10" />

        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-8 relative z-10">
          <div className="bg-cream-100/60 border-2 border-earth-700/10 rounded-[4px] p-6">
            <div className="flex items-center gap-2 text-text-muted text-[10px] uppercase font-semibold tracking-[0.2em] mb-3">
              <Wallet className="w-3.5 h-3.5" /> Net Equity
            </div>
            <div className="text-2xl font-bold text-earth-700 tabular-nums">{formatCurrency(stats.total_equity)}</div>
          </div>
          <div className="bg-cream-100/60 border-2 border-earth-700/10 rounded-[4px] p-6">
            <div className="flex items-center gap-2 text-text-muted text-[10px] uppercase font-semibold tracking-[0.2em] mb-3">
              <TrendingUp className="w-3.5 h-3.5 text-profit" /> Today
            </div>
            <div className={`text-2xl font-bold tabular-nums ${stats.today_pnl >= 0 ? 'text-profit' : 'text-loss'}`}>
              {stats.today_pnl >= 0 ? '+' : ''}{formatCurrency(stats.today_pnl)}
            </div>
          </div>
          <div className="bg-cream-100/60 border-2 border-earth-700/10 rounded-[4px] p-6">
            <div className="flex items-center gap-2 text-text-muted text-[10px] uppercase font-semibold tracking-[0.2em] mb-3">
              <Activity className="w-3.5 h-3.5" /> Win Rate
            </div>
            <div className="text-2xl font-bold text-earth-700 tabular-nums">{formatPercentage(stats.win_rate)}</div>
          </div>
          <div className="bg-cream-100/60 border-2 border-earth-700/10 rounded-[4px] p-6">
            <div className="text-text-muted text-[10px] uppercase font-semibold tracking-[0.2em] mb-3">PDT Status</div>
            <div className="text-2xl font-bold text-earth-700 tabular-nums">{stats.pdt_status}</div>
          </div>
        </div>

        {/* Return Summary */}
        <div className="flex justify-between items-center text-[10px] font-semibold text-text-dim uppercase tracking-[0.2em] bg-cream-100/60 px-6 py-4 rounded-[4px] border-2 border-earth-700/10 relative z-10">
          <span>Daily Return: {formatPercentage(stats.today_return)}</span>
          <div className="w-1 h-1 rounded-full bg-sakura-500/40" />
          <span>Generated: {new Date().toISOString()}</span>
        </div>
      </div>
    </ShareLayout>
  );
}
