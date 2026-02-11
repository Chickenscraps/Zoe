import { useState, useEffect } from 'react';
import type { Database } from '../lib/types';
import { Activity, TrendingUp, Droplets, Gauge, BarChart3 } from 'lucide-react';
import { supabase } from '../lib/supabaseClient';
import { MODE } from '../lib/mode';

type CandidateScan = Database['public']['Tables']['candidate_scans']['Row'];

const STRATEGY_COLORS: Record<string, string> = {
  momentum_long: 'text-profit',
  trend_follow_long: 'text-blue-400',
  mean_reversion: 'text-yellow-400',
  mean_reversion_long: 'text-yellow-300',
  take_profit: 'text-orange-400',
  hold: 'text-text-muted',
};

const STRATEGY_LABELS: Record<string, string> = {
  momentum_long: 'Momentum Long',
  trend_follow_long: 'Trend Follow',
  mean_reversion: 'Mean Reversion',
  mean_reversion_long: 'MR Long',
  take_profit: 'Take Profit',
  hold: 'Hold',
};

export default function Scanner() {
  const [candidates, setCandidates] = useState<CandidateScan[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchCandidates = async () => {
        try {
            setLoading(true);

            // Get latest scan batch: most recent created_at, then all from that batch
            const { data: latest } = await supabase
                .from('candidate_scans')
                .select('created_at')
                .eq('mode', MODE)
                .order('created_at', { ascending: false })
                .limit(1)
                .maybeSingle();

            if (!latest?.created_at) {
                setCandidates([]);
                return;
            }

            const { data, error } = await supabase
                .from('candidate_scans')
                .select('*')
                .eq('mode', MODE)
                .eq('created_at', latest.created_at)
                .order('score', { ascending: false });

            if (error) throw error;
            if (data) setCandidates(data);
        } catch (err) {
            console.error('Error fetching candidates:', err);
        } finally {
            setLoading(false);
        }
    };

    fetchCandidates();
    const interval = setInterval(fetchCandidates, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div className="text-text-secondary animate-pulse p-8">Scanning market...</div>;

  return (
    <div className="space-y-10">
      <div className="flex justify-between items-end border-b border-border pb-8">
          <div>
            <h2 className="text-3xl font-black text-white tracking-tighter">Market Scanner</h2>
            <p className="text-sm text-text-muted mt-2 font-medium tracking-tight">
              {candidates.length} symbols scored across liquidity, momentum, volatility &amp; trend.
            </p>
          </div>
          <div className="bg-surface-highlight/50 px-4 py-2 rounded-xl border border-border text-[10px] font-black text-white uppercase tracking-[0.2em]">
              {candidates[0]?.created_at ? `Last scan: ${new Date(candidates[0].created_at).toLocaleTimeString()}` : 'Waiting...'}
          </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {candidates.length > 0 ? candidates.map(candidate => {
              const breakdown = candidate.score_breakdown as any ?? {};
              const info = candidate.info as any ?? {};
              const strategy = candidate.recommended_strategy ?? 'hold';
              const hasTechnicals = info.has_technicals ?? false;

              return (
              <div key={candidate.id} className="card-premium p-8 group overflow-hidden relative">
                  <div className="absolute top-0 right-0 w-32 h-32 bg-white/[0.02] rounded-full -mr-16 -mt-16 transition-all group-hover:bg-white/[0.05]" />

                  <div className="flex justify-between items-start mb-6 relative z-10">
                      <div>
                          <h3 className="text-3xl font-black text-white tracking-tighter">{candidate.symbol}</h3>
                          <div className="flex gap-2 items-center mt-2">
                              <span className={`text-[10px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full border border-current/20 ${STRATEGY_COLORS[strategy] ?? 'text-text-muted'}`}>
                                  {STRATEGY_LABELS[strategy] ?? strategy}
                              </span>
                              {hasTechnicals ? (
                                  <span className="text-[9px] text-profit/60 font-bold uppercase tracking-widest">Live</span>
                              ) : (
                                  <span className="text-[9px] text-text-muted/40 font-bold uppercase tracking-widest">Warming</span>
                              )}
                          </div>
                      </div>
                      <div className="flex flex-col items-end">
                          <div className="text-4xl font-black text-white tracking-tighter tabular-nums">{Math.round(candidate.score ?? 0)}</div>
                          <div className="text-[10px] text-text-muted font-black uppercase tracking-[0.2em] mt-1">/100</div>
                      </div>
                  </div>

                  {/* 4-Component Score Bars */}
                  <div className="space-y-2.5 mb-6 relative z-10">
                      <ScoreBar label="Liquidity" value={breakdown.liquidity ?? 0} max={25} icon={<Droplets className="w-3 h-3" />} color="bg-blue-400" />
                      <ScoreBar label="Momentum" value={breakdown.momentum ?? 0} max={30} icon={<TrendingUp className="w-3 h-3" />} color="bg-profit" />
                      <ScoreBar label="Volatility" value={breakdown.volatility ?? 0} max={20} icon={<Gauge className="w-3 h-3" />} color="bg-yellow-400" />
                      <ScoreBar label="Trend" value={breakdown.trend ?? 0} max={25} icon={<BarChart3 className="w-3 h-3" />} color="bg-white/80" />
                  </div>

                  {/* Technical Indicators */}
                  <div className="pt-4 border-t border-border/50 space-y-2 relative z-10">
                      <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-[11px]">
                          <Indicator label="Spread" value={info.spread_pct != null ? `${info.spread_pct.toFixed(3)}%` : '--'} />
                          <Indicator label="RSI" value={info.rsi != null ? info.rsi.toFixed(0) : '--'} warn={info.rsi != null && (info.rsi > 70 || info.rsi < 30)} />
                          <Indicator label="Mom (15m)" value={info.momentum_short != null ? `${info.momentum_short > 0 ? '+' : ''}${info.momentum_short.toFixed(3)}%` : '--'} positive={info.momentum_short != null ? info.momentum_short > 0 : undefined} />
                          <Indicator label="Mom (1h)" value={info.momentum_medium != null ? `${info.momentum_medium > 0 ? '+' : ''}${info.momentum_medium.toFixed(3)}%` : '--'} positive={info.momentum_medium != null ? info.momentum_medium > 0 : undefined} />
                          <Indicator label="EMA Cross" value={info.ema_crossover != null ? `${info.ema_crossover > 0 ? '+' : ''}${info.ema_crossover.toFixed(3)}%` : '--'} positive={info.ema_crossover != null ? info.ema_crossover > 0 : undefined} />
                          <Indicator label="Trend R&sup2;" value={info.trend_strength != null ? info.trend_strength.toFixed(3) : '--'} />
                          <Indicator label="Vol (ann)" value={info.volatility_ann != null ? `${info.volatility_ann.toFixed(1)}%` : '--'} />
                          <Indicator label="Ticks" value={`${info.tick_count ?? 0}`} />
                      </div>
                  </div>
              </div>
              );
          }) : (
              <div className="col-span-full text-center py-20 text-text-muted italic border border-dashed border-border/50 rounded-cards bg-surface/50">
                  <Activity className="w-8 h-8 text-border mx-auto mb-4 opacity-50" />
                  No scan candidates found. Scanner initializing...
              </div>
          )}
      </div>
    </div>
  );
}

function ScoreBar({ label, value, max, icon, color }: { label: string; value: number; max: number; icon: React.ReactNode; color: string }) {
    const pct = Math.min(100, (value / max) * 100);
    return (
        <div className="flex items-center gap-2.5 text-[10px] font-black uppercase tracking-widest">
            <span className="w-[72px] text-text-muted flex items-center gap-1.5">{icon}{label}</span>
            <div className="flex-1 h-1.5 bg-background shadow-crisp rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
            </div>
            <span className="w-8 text-right text-text-secondary tabular-nums text-[9px]">{value.toFixed(0)}</span>
        </div>
    );
}

function Indicator({ label, value, positive, warn }: { label: string; value: string; positive?: boolean; warn?: boolean }) {
    let color = 'text-text-secondary';
    if (warn) color = 'text-orange-400';
    else if (positive === true) color = 'text-profit';
    else if (positive === false) color = 'text-loss';
    return (
        <div className="flex justify-between">
            <span className="text-text-muted font-medium">{label}</span>
            <span className={`font-bold tabular-nums ${color}`}>{value}</span>
        </div>
    );
}
