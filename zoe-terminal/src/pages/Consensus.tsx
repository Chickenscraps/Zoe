import { useState, useEffect } from 'react';
import type { Database } from '../lib/types';
import {
  Shield, ShieldOff, ShieldCheck,
  CheckCircle, XCircle, MinusCircle,
  TrendingUp, TrendingDown,
  AlertTriangle, Zap,
} from 'lucide-react';
import { supabase } from '../lib/supabaseClient';
import { useModeContext } from '../lib/mode';
import { cn } from '../lib/utils';

type CandidateScan = Database['public']['Tables']['candidate_scans']['Row'];

const GATE_NAMES = [
  'Technical Alignment',
  'Volatility Environment',
  'MTF Agreement',
  'Bollinger Confirmation',
  'Divergence Check',
  'Liquidity Health',
  'Regime Consistency',
];

const CONSENSUS_STYLES: Record<string, { bg: string; text: string; border: string; icon: typeof Shield }> = {
  strong_buy: { bg: 'bg-profit/15', text: 'text-profit', border: 'border-profit/30', icon: ShieldCheck },
  buy: { bg: 'bg-profit/10', text: 'text-profit/80', border: 'border-profit/20', icon: Shield },
  neutral: { bg: 'bg-yellow-400/10', text: 'text-yellow-400', border: 'border-yellow-400/20', icon: MinusCircle },
  sell: { bg: 'bg-loss/10', text: 'text-loss/80', border: 'border-loss/20', icon: Shield },
  strong_sell: { bg: 'bg-loss/15', text: 'text-loss', border: 'border-loss/30', icon: ShieldOff },
  blocked: { bg: 'bg-red-500/15', text: 'text-red-400', border: 'border-red-500/30', icon: ShieldOff },
};

export default function Consensus() {
  const { mode } = useModeContext();
  const [candidates, setCandidates] = useState<CandidateScan[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const { data: latest } = await supabase
          .from('candidate_scans')
          .select('created_at')
          .eq('mode', mode)
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
          .eq('mode', mode)
          .eq('created_at', latest.created_at)
          .order('score', { ascending: false });

        if (error) throw error;
        if (data) setCandidates(data);
      } catch (err) {
        console.error('Error fetching consensus data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [mode]);

  if (loading) {
    return <div className="text-text-secondary animate-pulse p-8">Loading consensus engine data...</div>;
  }

  return (
    <div className="space-y-6 sm:space-y-10">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-2 border-b border-border pb-4 sm:pb-8">
        <div>
          <h2 className="text-2xl sm:text-3xl font-black text-white tracking-tighter">Consensus Engine</h2>
          <p className="text-xs sm:text-sm text-text-muted mt-1 sm:mt-2 font-medium tracking-tight">
            7-gate validation framework with kill switch. All gates must align for trade execution.
          </p>
        </div>
        <div className="bg-surface-highlight/50 px-3 py-1.5 rounded-xl border border-border text-[9px] sm:text-[10px] font-black text-white uppercase tracking-[0.15em] sm:tracking-[0.2em]">
          {candidates[0]?.created_at ? `Scan: ${new Date(candidates[0].created_at).toLocaleTimeString()}` : 'Waiting...'}
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
        {(() => {
          const results = candidates.map(c => (c.info as any)?.consensus?.result).filter(Boolean);
          const blocked = results.filter(r => r === 'blocked').length;
          const buys = results.filter(r => r === 'buy' || r === 'strong_buy').length;
          const sells = results.filter(r => r === 'sell' || r === 'strong_sell').length;
          const neutral = results.filter(r => r === 'neutral').length;

          return (
            <>
              <StatCard label="Buy Signals" value={buys} color="text-profit" icon={<TrendingUp className="w-4 h-4" />} />
              <StatCard label="Sell Signals" value={sells} color="text-loss" icon={<TrendingDown className="w-4 h-4" />} />
              <StatCard label="Neutral" value={neutral} color="text-yellow-400" icon={<MinusCircle className="w-4 h-4" />} />
              <StatCard label="Blocked" value={blocked} color="text-red-400" icon={<ShieldOff className="w-4 h-4" />} />
            </>
          );
        })()}
      </div>

      {/* Per-Symbol Consensus Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        {candidates.length > 0 ? candidates.map(candidate => {
          const info = candidate.info as any ?? {};
          const consensus = info.consensus;
          const regime = info.regime;

          if (!consensus) {
            return (
              <div key={candidate.id} className="card-premium p-4 sm:p-6 opacity-50">
                <div className="flex items-center gap-3">
                  <h3 className="text-xl font-black text-white tracking-tighter">{candidate.symbol}</h3>
                  <span className="text-[10px] text-text-muted font-bold uppercase tracking-widest">No consensus data</span>
                </div>
              </div>
            );
          }

          const style = CONSENSUS_STYLES[consensus.result] ?? CONSENSUS_STYLES.neutral;
          const ResultIcon = style.icon;

          return (
            <div key={candidate.id} className="card-premium p-4 sm:p-6 space-y-4">
              {/* Header */}
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 sm:gap-3 flex-wrap min-w-0">
                  <h3 className="text-lg sm:text-xl font-black text-white tracking-tighter">{candidate.symbol}</h3>
                  {regime && (
                    <span className={cn(
                      'text-[9px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full border',
                      regime.regime === 'bull' ? 'bg-profit/10 text-profit border-profit/20'
                        : regime.regime === 'bear' ? 'bg-loss/10 text-loss border-loss/20'
                        : regime.regime === 'high_vol' ? 'bg-orange-400/10 text-orange-400 border-orange-400/20'
                        : 'bg-yellow-400/10 text-yellow-400 border-yellow-400/20'
                    )}>
                      {regime.regime}
                    </span>
                  )}
                </div>
                <div className={cn(
                  'flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-black uppercase tracking-wider',
                  style.bg, style.text, style.border
                )}>
                  <ResultIcon className="w-4 h-4" />
                  {consensus.result.replace(/_/g, ' ')}
                </div>
              </div>

              {/* Gate Progress */}
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-text-muted font-bold">Gates Passed</span>
                <span className="font-black text-white tabular-nums">{consensus.gates_passed}/{consensus.gates_total}</span>
              </div>
              <div className="h-2 bg-background rounded-full overflow-hidden">
                <div
                  className={cn(
                    'h-full rounded-full transition-all',
                    consensus.confidence > 0.7 ? 'bg-profit'
                      : consensus.confidence > 0.4 ? 'bg-yellow-400'
                      : 'bg-loss'
                  )}
                  style={{ width: `${(consensus.gates_passed / consensus.gates_total) * 100}%` }}
                />
              </div>

              {/* 7-Gate Visualization */}
              <div className="grid grid-cols-1 gap-1.5">
                {GATE_NAMES.map((gateName, i) => {
                  // Determine gate status from supporting/blocking reasons
                  const isSupporting = consensus.supporting_reasons?.some((r: string) =>
                    matchesGate(r, i)
                  );
                  const isBlocking = consensus.blocking_reasons?.some((r: string) =>
                    matchesGate(r, i)
                  );

                  return (
                    <div key={gateName} className="flex items-center gap-2">
                      {isSupporting ? (
                        <CheckCircle className="w-3.5 h-3.5 text-profit flex-shrink-0" />
                      ) : isBlocking ? (
                        <XCircle className="w-3.5 h-3.5 text-loss flex-shrink-0" />
                      ) : (
                        <MinusCircle className="w-3.5 h-3.5 text-text-muted/40 flex-shrink-0" />
                      )}
                      <span className={cn(
                        'text-[10px] font-medium',
                        isSupporting ? 'text-profit/80' : isBlocking ? 'text-loss/80' : 'text-text-muted/50'
                      )}>
                        {gateName}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Reasons */}
              {(consensus.supporting_reasons?.length > 0 || consensus.blocking_reasons?.length > 0) && (
                <div className="pt-3 border-t border-border/30 space-y-2">
                  {consensus.supporting_reasons?.slice(0, 3).map((r: string, i: number) => (
                    <div key={`s-${i}`} className="flex items-start gap-1.5">
                      <Zap className="w-3 h-3 text-profit/60 mt-0.5 flex-shrink-0" />
                      <span className="text-[9px] text-profit/70 font-medium">{r}</span>
                    </div>
                  ))}
                  {consensus.blocking_reasons?.slice(0, 3).map((r: string, i: number) => (
                    <div key={`b-${i}`} className="flex items-start gap-1.5">
                      <AlertTriangle className="w-3 h-3 text-red-400/60 mt-0.5 flex-shrink-0" />
                      <span className="text-[9px] text-red-400/70 font-medium">{r}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        }) : (
          <div className="col-span-full text-center py-20 text-text-muted italic border border-dashed border-border/50 rounded-cards bg-surface/50">
            <Shield className="w-8 h-8 text-border mx-auto mb-4 opacity-50" />
            No consensus data available. Scanner initializing...
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, color, icon }: { label: string; value: number; color: string; icon: React.ReactNode }) {
  return (
    <div className="card-premium p-4 flex items-center justify-between">
      <div>
        <div className="text-[10px] text-text-muted font-bold uppercase tracking-widest">{label}</div>
        <div className={cn('text-2xl font-black tabular-nums mt-1', color)}>{value}</div>
      </div>
      <div className={cn('opacity-40', color)}>{icon}</div>
    </div>
  );
}

/**
 * Match a reason string to one of the 7 gates by keyword.
 */
function matchesGate(reason: string, gateIndex: number): boolean {
  const lc = reason.toLowerCase();
  switch (gateIndex) {
    case 0: // Technical Alignment
      return lc.includes('indicator') || lc.includes('aligned') || lc.includes('technical') || lc.includes('conflict');
    case 1: // Volatility
      return lc.includes('volatil') || lc.includes('erratic');
    case 2: // MTF
      return lc.includes('mtf') || lc.includes('timeframe') || lc.includes('indecisive');
    case 3: // Bollinger
      return lc.includes('bb ') || lc.includes('bollinger') || lc.includes('%b') || lc.includes('overbought') || lc.includes('oversold');
    case 4: // Divergence
      return lc.includes('divergen');
    case 5: // Liquidity
      return lc.includes('liquid') || lc.includes('spread');
    case 6: // Regime
      return lc.includes('regime') || lc.includes('bull') || lc.includes('bear');
    default:
      return false;
  }
}
