/**
 * Intelligence — unified command center merging Plan, Consensus, Structure & Thoughts
 * into a single page with no duplicate information.
 */

import { useState, useEffect, useMemo } from 'react';
import type { Database } from '../lib/types';
import {
  Target, Zap, ShieldCheck, ShieldOff, Shield,
  DollarSign, TrendingUp, TrendingDown, Minus, MinusCircle, XCircle,
  RotateCcw, ArrowUpRight, ArrowDownRight, ShieldX, CircleDot,
  BrainCircuit, Filter, AlertTriangle, Map, Layers, SearchX, CheckCircle2 as CheckCircle,
} from 'lucide-react';
import { supabase } from '../lib/supabaseClient';

import { useDashboardData } from '../hooks/useDashboardData';
import { useStructureData, type BounceIntent } from '../hooks/useStructureData';
import { formatCurrency, formatDate, cn } from '../lib/utils';
import { Skeleton } from '../components/Skeleton';
import { StatusChip } from '../components/StatusChip';

type CandidateScan = Database['public']['Tables']['candidate_scans']['Row'];
type Thought = Database['public']['Tables']['thoughts']['Row'];

// ── Sections ──────────────────────────────────────────────────────────

type Section = 'plan' | 'consensus' | 'structure' | 'thoughts';

const SECTIONS: { id: Section; label: string; icon: typeof Map }[] = [
  { id: 'plan', label: 'Gameplan', icon: Map },
  { id: 'consensus', label: 'Consensus', icon: Shield },
  { id: 'structure', label: 'Structure', icon: Layers },
  { id: 'thoughts', label: 'Thoughts', icon: BrainCircuit },
];

// ── Gate matching (from Consensus) ────────────────────────────────────

const GATE_NAMES = [
  'Technical Alignment', 'Volatility Environment', 'MTF Agreement',
  'Bollinger Confirmation', 'Divergence Check', 'Liquidity Health', 'Regime Consistency',
];

function matchesGate(reason: string, gateIndex: number): boolean {
  const lc = reason.toLowerCase();
  switch (gateIndex) {
    case 0: return lc.includes('indicator') || lc.includes('aligned') || lc.includes('technical') || lc.includes('conflict');
    case 1: return lc.includes('volatil') || lc.includes('erratic');
    case 2: return lc.includes('mtf') || lc.includes('timeframe') || lc.includes('indecisive');
    case 3: return lc.includes('bb ') || lc.includes('bollinger') || lc.includes('%b') || lc.includes('overbought') || lc.includes('oversold');
    case 4: return lc.includes('divergen');
    case 5: return lc.includes('liquid') || lc.includes('spread');
    case 6: return lc.includes('regime') || lc.includes('bull') || lc.includes('bear');
    default: return false;
  }
}

// ── Consensus styles ──────────────────────────────────────────────────

const CONSENSUS_STYLES: Record<string, { bg: string; text: string; border: string; icon: typeof Shield }> = {
  strong_buy: { bg: 'bg-profit/15', text: 'text-profit', border: 'border-profit/30', icon: ShieldCheck },
  buy: { bg: 'bg-profit/10', text: 'text-profit/80', border: 'border-profit/20', icon: Shield },
  neutral: { bg: 'bg-yellow-400/10', text: 'text-yellow-400', border: 'border-yellow-400/20', icon: MinusCircle },
  sell: { bg: 'bg-loss/10', text: 'text-loss/80', border: 'border-loss/20', icon: Shield },
  strong_sell: { bg: 'bg-loss/15', text: 'text-loss', border: 'border-loss/30', icon: ShieldOff },
  blocked: { bg: 'bg-red-500/15', text: 'text-red-400', border: 'border-red-500/30', icon: ShieldOff },
};

// ── Thought type config ───────────────────────────────────────────────

const TYPE_CONFIG: Record<string, { bg: string; text: string; label: string }> = {
  scan:        { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: 'Scan' },
  signal:      { bg: 'bg-profit/20',     text: 'text-profit',     label: 'Signal' },
  paper_trade: { bg: 'bg-blue-500/20',   text: 'text-blue-400',   label: 'Simulation' },
  order:       { bg: 'bg-profit/20',     text: 'text-profit',     label: 'Order' },
  order_error: { bg: 'bg-loss/20',       text: 'text-loss',       label: 'Error' },
  entry:       { bg: 'bg-blue-500/20',   text: 'text-blue-400',   label: 'Entry' },
  exit:        { bg: 'bg-purple-500/20', text: 'text-purple-400', label: 'Exit' },
  health:      { bg: 'bg-red-500/20',    text: 'text-red-400',    label: 'Health' },
  general:     { bg: 'bg-surface-highlight', text: 'text-text-secondary', label: 'General' },
};

// ── Structure filters ─────────────────────────────────────────────────

const SYMBOLS = ['All', 'BTC-USD', 'ETH-USD', 'SOL-USD', 'DOGE-USD', 'AVAX-USD'];
const TIMEFRAMES = ['All', '15m', '1h', '4h', '1d'];

// ═══════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════

export default function Intelligence() {
  const [activeSection, setActiveSection] = useState<Section>('plan');

  // ── Plan state ────────────────────────────────────────────────────
  const [candidates, setCandidates] = useState<CandidateScan[]>([]);
  const [planLoading, setPlanLoading] = useState(true);

  // ── Consensus state ───────────────────────────────────────────────
  const [consensusCandidates, setConsensusCandidates] = useState<CandidateScan[]>([]);
  const [consensusLoading, setConsensusLoading] = useState(true);

  // ── Thoughts state ────────────────────────────────────────────────
  const [thoughts, setThoughts] = useState<Thought[]>([]);
  const [filterType, setFilterType] = useState<string>('all');
  const [thoughtsLoading, setThoughtsLoading] = useState(true);

  // ── Structure state ───────────────────────────────────────────────
  const [structSymbol, setStructSymbol] = useState('All');
  const [structTimeframe, setStructTimeframe] = useState('All');

  // ── Hooks ─────────────────────────────────────────────────────────
  const {
    cryptoCash, holdingsRows, healthSummary, dailyNotional, realizedPnl,
    loading: dashLoading,
  } = useDashboardData();

  const {
    trendlines, levels, structureEvents, bounceEvents, bounceIntents, pivots,
    loading: structLoading,
  } = useStructureData({
    symbol: structSymbol === 'All' ? undefined : structSymbol,
    timeframe: structTimeframe === 'All' ? undefined : structTimeframe,
  });

  // ── Fetch scanner candidates ──────────────────────────────────────
  useEffect(() => {
    const fetchCandidates = async () => {
      try {
        setPlanLoading(true);
        const { data: scans } = await supabase
          .from('candidate_scans')
          .select('*')
          .order('created_at', { ascending: false })
          .limit(12);
        if (scans) setCandidates(scans);
      } catch (err) {
        console.error('Error fetching candidates:', err);
      } finally {
        setPlanLoading(false);
      }
    };
    fetchCandidates();
    const interval = setInterval(fetchCandidates, 30000);
    return () => clearInterval(interval);
  }, []);

  // ── Fetch consensus data ──────────────────────────────────────────
  useEffect(() => {
    const fetchConsensus = async () => {
      try {
        setConsensusLoading(true);
        const { data: latest } = await supabase
          .from('candidate_scans')
          .select('created_at')
          .order('created_at', { ascending: false })
          .limit(1)
          .maybeSingle();

        if (!latest?.created_at) { setConsensusCandidates([]); return; }

        const { data } = await supabase
          .from('candidate_scans')
          .select('*')
          .eq('created_at', latest.created_at)
          .order('score', { ascending: false });
        if (data) setConsensusCandidates(data);
      } catch (err) {
        console.error('Error fetching consensus:', err);
      } finally {
        setConsensusLoading(false);
      }
    };
    fetchConsensus();
    const interval = setInterval(fetchConsensus, 30000);
    return () => clearInterval(interval);
  }, []);

  // ── Fetch thoughts ────────────────────────────────────────────────
  useEffect(() => {
    const fetchThoughts = async () => {
      try {
        setThoughtsLoading(true);
        const { data } = await supabase
          .from('thoughts')
          .select('*')
          .order('created_at', { ascending: false })
          .limit(50);
        if (data) setThoughts(data);
      } catch (err) {
        console.error('Error fetching thoughts:', err);
      } finally {
        setThoughtsLoading(false);
      }
    };
    fetchThoughts();
    const interval = setInterval(fetchThoughts, 15000);
    return () => clearInterval(interval);
  }, []);

  // ── Derived data ──────────────────────────────────────────────────
  const scannerRows = useMemo(() => {
    return candidates
      .sort((a, b) => b.score - a.score)
      .map((c) => {
        const info = c.info as any;
        const breakdown = c.score_breakdown as any;
        return {
          symbol: c.symbol, score: c.score,
          strategy: c.recommended_strategy,
          catalyst: info?.catalyst && info.catalyst !== 'none' ? info.catalyst : null,
          regime: info?.sector ?? 'Crypto',
          ivr: info?.ivr ?? '—',
          trend: breakdown?.trend ?? 0,
          momentum: breakdown?.momentum ?? 0,
          volatility: breakdown?.volatility ?? 0,
          liquidity: breakdown?.liquidity ?? 0,
          tier: c.score >= 40 ? 'Tier 1' : 'Tier 2',
        };
      });
  }, [candidates]);

  const filteredThoughts = filterType === 'all' ? thoughts : thoughts.filter(t => t.type === filterType);
  const availableTypes = Array.from(new Set(thoughts.map(t => t.type))).sort();

  const cashAvailable = cryptoCash?.cash_available ?? 0;
  const buyingPower = cryptoCash?.buying_power ?? 0;
  const notionalUsed = dailyNotional?.notional_used ?? 0;

  // ═════════════════════════════════════════════════════════════════════
  // RENDER
  // ═════════════════════════════════════════════════════════════════════

  return (
    <div className="space-y-6 sm:space-y-10">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-2 border-b border-earth-700/10 pb-4 sm:pb-8">
        <div>
          <h2 className="font-pixel text-[0.65rem] uppercase tracking-[0.08em] text-earth-700">Intelligence Center</h2>
          <p className="text-xs sm:text-sm text-text-muted mt-1 sm:mt-2 font-medium tracking-tight">
            Unified view — gameplan, consensus gates, market structure & system thoughts.
          </p>
        </div>
        <div className="flex items-center gap-2 sm:gap-4">
          <div className={cn(
            "px-2 sm:px-3 py-1.5 rounded-full border text-[9px] sm:text-[10px] font-black uppercase tracking-widest",
            healthSummary.status === 'LIVE' ? "bg-profit/10 text-profit border-profit/20" : "bg-warning/10 text-warning border-warning/20"
          )}>
            {healthSummary.status}
          </div>
          <div className="text-[9px] sm:text-[10px] font-black text-text-muted uppercase tracking-[0.15em] sm:tracking-[0.2em] hidden sm:block">
            {new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}
          </div>
        </div>
      </div>

      {/* Section Tabs */}
      <div className="flex gap-3 sm:gap-6 border-b border-earth-700/10 overflow-x-auto">
        {SECTIONS.map((sec) => (
          <button
            key={sec.id}
            onClick={() => setActiveSection(sec.id)}
            className={cn(
              "pb-3 sm:pb-4 text-[9px] sm:text-[10px] font-black uppercase tracking-[0.15em] sm:tracking-[0.2em] flex items-center gap-1.5 sm:gap-2 border-b-2 transition-all duration-300 whitespace-nowrap",
              activeSection === sec.id
                ? "border-sakura-500 text-earth-700"
                : "border-transparent text-text-muted hover:text-text-secondary"
            )}
          >
            <sec.icon className={cn("w-3 sm:w-3.5 h-3 sm:h-3.5", activeSection === sec.id ? "text-sakura-700" : "")} />
            {sec.label}
          </button>
        ))}
      </div>

      {/* ═══════════════ PLAN SECTION ═══════════════ */}
      {activeSection === 'plan' && (
        <div className="space-y-6 sm:space-y-8">
          {/* KPI Strip */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            <KPIBlock icon={DollarSign} label="Cash Available" value={formatCurrency(cashAvailable)} color="profit" />
            <KPIBlock icon={TrendingUp} label="Buying Power" value={formatCurrency(buyingPower)} color="white" />
            <KPIBlock icon={DollarSign} label="Realized P&L" value={formatCurrency(realizedPnl)} color={realizedPnl >= 0 ? 'profit' : 'loss'} />
            <KPIBlock icon={ShieldCheck} label="System Status" value={healthSummary.status} color={healthSummary.status === 'LIVE' ? 'profit' : 'warning'} />
          </div>

          {/* Scanner Candidates */}
          {planLoading || dashLoading ? (
            <div className="flex flex-col items-center justify-center h-48 text-text-muted animate-pulse gap-4">
              <div className="w-10 h-10 border-2 border-earth-700/10 border-t-sakura-500 rounded-full animate-spin" />
              <span className="text-[10px] font-black uppercase tracking-widest italic">Interpreting market signals...</span>
            </div>
          ) : scannerRows.length > 0 ? (
            <>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
                {scannerRows.map((row) => (
                  <div key={row.symbol} className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] p-4 sm:p-6 group overflow-hidden relative">
                    <div className="absolute top-0 right-0 w-24 h-24 bg-sakura-500/[0.03] rounded-full -mr-12 -mt-12 transition-all group-hover:bg-sakura-500/[0.06]" />
                    <div className="flex justify-between items-start mb-4 sm:mb-5 relative z-10">
                      <div>
                        <h3 className="text-xl sm:text-2xl font-black text-earth-700 tracking-tighter">{row.symbol}</h3>
                        <div className="flex gap-2 text-[9px] sm:text-[10px] text-text-muted mt-1 font-black uppercase tracking-widest">
                          <span className="text-earth-700/40">{row.regime}</span>
                          <span className="opacity-30">|</span>
                          <span className="text-earth-700/40">IVR {row.ivr}</span>
                        </div>
                      </div>
                      <div className="flex flex-col items-end">
                        <div className="text-2xl sm:text-3xl font-black text-earth-700 tracking-tighter tabular-nums">{row.score}</div>
                        <div className="text-[9px] text-text-muted font-black uppercase tracking-[0.15em]">/100</div>
                      </div>
                    </div>
                    <div className="space-y-2 mb-4 sm:mb-5 relative z-10">
                      {[
                        { label: 'Trend', value: row.trend, max: 25, color: 'bg-earth-700/50' },
                        { label: 'Momentum', value: row.momentum, max: 30, color: 'bg-profit' },
                        { label: 'Volatility', value: row.volatility, max: 25, color: 'bg-warning' },
                        { label: 'Liquidity', value: row.liquidity, max: 25, color: 'bg-blue-400' },
                      ].map((bar) => (
                        <div key={bar.label} className="flex items-center gap-2 sm:gap-3 text-[9px] sm:text-[10px] font-black uppercase tracking-widest">
                          <span className="w-16 sm:w-20 text-text-muted">{bar.label}</span>
                          <div className="flex-1 h-1.5 bg-cream-100/80 rounded-full overflow-hidden">
                            <div className={cn("h-full rounded-full", bar.color)} style={{ width: `${(bar.value / bar.max) * 100}%` }} />
                          </div>
                          <span className="w-6 text-right text-text-muted tabular-nums">{bar.value}</span>
                        </div>
                      ))}
                    </div>
                    <div className="pt-3 sm:pt-4 border-t border-earth-700/10 space-y-2 sm:space-y-3 relative z-10">
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-text-muted font-black uppercase tracking-widest flex items-center gap-2">
                          <Target className="w-3 h-3 text-profit" /> Strategy
                        </span>
                        <span className="text-earth-700 font-black uppercase tracking-tight">{row.strategy}</span>
                      </div>
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-text-muted font-black uppercase tracking-widest flex items-center gap-2">
                          <ShieldCheck className="w-3 h-3" /> Risk Tier
                        </span>
                        <span className={cn(
                          "text-[10px] px-3 py-1 rounded-full border font-black uppercase tracking-widest",
                          row.tier === 'Tier 1' ? "bg-profit/10 text-profit border-profit/20" : "bg-warning/10 text-warning border-warning/20"
                        )}>{row.tier}</span>
                      </div>
                      {row.catalyst && (
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-text-muted font-black uppercase tracking-widest flex items-center gap-2">
                            <Zap className="w-3 h-3 text-warning" /> Catalyst
                          </span>
                          <span className="text-warning font-black uppercase tracking-tight">{row.catalyst}</span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Holdings + Notional */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
                <div className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] p-4 sm:p-6">
                  <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-4 sm:mb-5">Current Holdings</h3>
                  <div className="space-y-2">
                    {holdingsRows.length > 0 ? holdingsRows.map((h) => (
                      <div key={h.asset} className="flex justify-between items-center text-xs bg-cream-100/60 border-2 border-earth-700/10 rounded-[4px] px-3 sm:px-4 py-2.5">
                        <span className="font-black text-earth-700">{h.asset}</span>
                        <div className="flex gap-3 sm:gap-6">
                          <span className="font-mono text-text-secondary tabular-nums">{h.qty.toFixed(8)}</span>
                          <span className="font-mono text-text-muted tabular-nums w-14 text-right">{h.allocation.toFixed(1)}%</span>
                        </div>
                      </div>
                    )) : (
                      <div className="text-text-dim text-xs italic">No holdings snapshot available.</div>
                    )}
                  </div>
                </div>
                <div className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] p-4 sm:p-5 flex justify-between items-center">
                  <div className="flex items-center gap-3">
                    <ShieldCheck className="w-4 h-4 text-text-muted" />
                    <span className="text-[9px] sm:text-[10px] font-black text-text-muted uppercase tracking-[0.15em] sm:tracking-[0.2em]">Daily Notional Used</span>
                  </div>
                  <span className="text-sm font-black text-earth-700 tabular-nums">{formatCurrency(notionalUsed)}</span>
                </div>
              </div>
            </>
          ) : (
            <EmptyPanel icon={SearchX} text="Awaiting Scanner Data" sub="Scanner will populate candidates on next cycle." />
          )}
        </div>
      )}

      {/* ═══════════════ CONSENSUS SECTION ═══════════════ */}
      {activeSection === 'consensus' && (
        <div className="space-y-6 sm:space-y-8">
          {consensusLoading ? (
            <div className="animate-pulse py-12 text-center text-text-muted text-xs">Loading consensus engine...</div>
          ) : (
            <>
              {/* Summary stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
                {(() => {
                  const results = consensusCandidates.map(c => (c.info as any)?.consensus?.result).filter(Boolean);
                  return (
                    <>
                      <StatCard label="Buy Signals" value={results.filter(r => r === 'buy' || r === 'strong_buy').length} color="text-profit" icon={<TrendingUp className="w-4 h-4" />} />
                      <StatCard label="Sell Signals" value={results.filter(r => r === 'sell' || r === 'strong_sell').length} color="text-loss" icon={<TrendingDown className="w-4 h-4" />} />
                      <StatCard label="Neutral" value={results.filter(r => r === 'neutral').length} color="text-yellow-400" icon={<MinusCircle className="w-4 h-4" />} />
                      <StatCard label="Blocked" value={results.filter(r => r === 'blocked').length} color="text-red-400" icon={<ShieldOff className="w-4 h-4" />} />
                    </>
                  );
                })()}
              </div>

              {/* Per-symbol cards */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
                {consensusCandidates.length > 0 ? consensusCandidates.map(candidate => {
                  const info = candidate.info as any ?? {};
                  const consensus = info.consensus;
                  const regime = info.regime;
                  if (!consensus) {
                    return (
                      <div key={candidate.id} className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] p-4 sm:p-6 opacity-50">
                        <div className="flex items-center gap-3">
                          <h3 className="text-lg sm:text-xl font-black text-earth-700 tracking-tighter">{candidate.symbol}</h3>
                          <span className="text-[10px] text-text-muted font-bold uppercase tracking-widest">No consensus data</span>
                        </div>
                      </div>
                    );
                  }
                  const style = CONSENSUS_STYLES[consensus.result] ?? CONSENSUS_STYLES.neutral;
                  const ResultIcon = style.icon;
                  return (
                    <div key={candidate.id} className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] p-4 sm:p-6 space-y-4">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 sm:gap-3 flex-wrap min-w-0">
                          <h3 className="text-lg sm:text-xl font-black text-earth-700 tracking-tighter">{candidate.symbol}</h3>
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
                      <div className="flex items-center justify-between text-[10px]">
                        <span className="text-text-muted font-bold">Gates Passed</span>
                        <span className="font-black text-earth-700 tabular-nums">{consensus.gates_passed}/{consensus.gates_total}</span>
                      </div>
                      <div className="h-2 bg-cream-100/80 rounded-full overflow-hidden">
                        <div
                          className={cn(
                            'h-full rounded-full transition-all',
                            consensus.confidence > 0.7 ? 'bg-profit' : consensus.confidence > 0.4 ? 'bg-yellow-400' : 'bg-loss'
                          )}
                          style={{ width: `${(consensus.gates_passed / consensus.gates_total) * 100}%` }}
                        />
                      </div>
                      <div className="grid grid-cols-1 gap-1.5">
                        {GATE_NAMES.map((gateName, i) => {
                          const isSupporting = consensus.supporting_reasons?.some((r: string) => matchesGate(r, i));
                          const isBlocking = consensus.blocking_reasons?.some((r: string) => matchesGate(r, i));
                          return (
                            <div key={gateName} className="flex items-center gap-2">
                              {isSupporting ? <CheckCircle className="w-3.5 h-3.5 text-profit flex-shrink-0" />
                                : isBlocking ? <XCircle className="w-3.5 h-3.5 text-loss flex-shrink-0" />
                                : <MinusCircle className="w-3.5 h-3.5 text-text-muted/40 flex-shrink-0" />}
                              <span className={cn('text-[10px] font-medium', isSupporting ? 'text-profit/80' : isBlocking ? 'text-loss/80' : 'text-text-muted/50')}>
                                {gateName}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                      {(consensus.supporting_reasons?.length > 0 || consensus.blocking_reasons?.length > 0) && (
                        <div className="pt-3 border-t border-earth-700/10 space-y-2">
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
                  <EmptyPanel icon={Shield} text="No consensus data available" sub="Scanner initializing..." />
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* ═══════════════ STRUCTURE SECTION ═══════════════ */}
      {activeSection === 'structure' && (
        <div className="space-y-6 sm:space-y-8">
          {/* Filters */}
          <div className="flex flex-col sm:flex-row flex-wrap items-start sm:items-center gap-3">
            <FilterBar label="Symbol" items={SYMBOLS} active={structSymbol} onSelect={setStructSymbol} />
            <div className="h-6 w-px bg-earth-700/10 hidden sm:block" />
            <FilterBar label="TF" items={TIMEFRAMES} active={structTimeframe} onSelect={setStructTimeframe} />
          </div>

          {/* Summary counters */}
          <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-2 sm:gap-4">
            <SummaryStat label="Trendlines" value={trendlines.length} icon={TrendingUp} />
            <SummaryStat label="Levels" value={levels.length} icon={Minus} />
            <SummaryStat label="Pivots" value={pivots.length} icon={CircleDot} />
            <SummaryStat label="Events" value={structureEvents.length} icon={Zap} />
            <SummaryStat label="Bounces" value={bounceEvents.length} icon={RotateCcw} />
            <SummaryStat label="Intents" value={bounceIntents.length} icon={Target} />
          </div>

          {structLoading ? (
            <div className="space-y-4 animate-pulse">
              {[1, 2].map(i => <Skeleton key={i} className="h-64" />)}
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-8">
                {/* Trendlines */}
                <div className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] p-4 sm:p-8">
                  <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-6 flex items-center gap-2">
                    <TrendingUp className="w-3 h-3 text-profit" /> Active Trendlines
                  </h3>
                  <div className="space-y-2 max-h-[350px] overflow-y-auto pr-1">
                    {trendlines.length > 0 ? trendlines.map((tl) => (
                      <div key={tl.id} className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-2 sm:gap-3 bg-cream-100/60 border-2 border-earth-700/10 rounded-[4px] px-3 sm:px-4 py-2.5 sm:py-3 text-xs">
                        <div className="flex items-center gap-2">
                          {tl.side === 'support' ? <TrendingUp className="w-3 h-3 text-profit" /> : <TrendingDown className="w-3 h-3 text-loss" />}
                          <span className="font-black text-earth-700">{tl.symbol}</span>
                          <span className="text-text-muted text-[10px] font-mono">{tl.timeframe}</span>
                        </div>
                        <span className={cn("text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full", tl.side === 'support' ? "bg-profit/10 text-profit" : "bg-loss/10 text-loss")}>{tl.side}</span>
                        <span className="font-mono text-text-secondary text-right">{tl.inlier_count} pts</span>
                        <ScoreBadge score={tl.score} />
                      </div>
                    )) : <EmptyRow text="No active trendlines detected yet" />}
                  </div>
                </div>

                {/* Key Levels */}
                <div className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] p-4 sm:p-8">
                  <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-6 flex items-center gap-2">
                    <Minus className="w-3 h-3 text-warning" /> Key Levels
                  </h3>
                  <div className="space-y-2 max-h-[350px] overflow-y-auto pr-1">
                    {levels.length > 0 ? levels.map((lv) => (
                      <div key={lv.id} className="grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-2 sm:gap-3 bg-cream-100/60 border-2 border-earth-700/10 rounded-[4px] px-3 sm:px-4 py-2.5 sm:py-3 text-xs">
                        <div className="flex items-center gap-2">
                          <span className="font-black text-earth-700">{lv.symbol}</span>
                          <span className="text-text-muted text-[10px] font-mono">{lv.timeframe}</span>
                        </div>
                        <span className="font-mono text-earth-700 font-bold">{formatCurrency(lv.price_centroid)}</span>
                        <span className={cn("text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full",
                          lv.role === 'support' ? "bg-profit/10 text-profit" : lv.role === 'resistance' ? "bg-loss/10 text-loss" : "bg-warning/10 text-warning"
                        )}>{lv.role ?? '—'}</span>
                        <span className="font-mono text-text-secondary">{lv.touch_count}x</span>
                        <ScoreBadge score={lv.score} />
                      </div>
                    )) : <EmptyRow text="No horizontal levels clustered yet" />}
                  </div>
                </div>

                {/* Structure Events */}
                <div className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] p-4 sm:p-8">
                  <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-6 flex items-center gap-2">
                    <Zap className="w-3 h-3 text-warning" /> Structure Events
                  </h3>
                  <div className="space-y-3 max-h-[350px] overflow-y-auto pr-1">
                    {structureEvents.length > 0 ? structureEvents.map((ev) => (
                      <div key={ev.id} className="flex items-center gap-3 bg-cream-100/60 border-2 border-earth-700/10 rounded-[4px] px-3 sm:px-4 py-2.5 sm:py-3">
                        <EventIcon type={ev.event_type as 'breakout' | 'breakdown' | 'retest'} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs font-black text-earth-700">{ev.symbol}</span>
                            <span className="text-[10px] font-mono text-text-muted">{ev.timeframe}</span>
                            <span className={cn("text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full",
                              ev.event_type === 'breakout' ? "bg-profit/10 text-profit" : ev.event_type === 'breakdown' ? "bg-loss/10 text-loss" : "bg-warning/10 text-warning"
                            )}>{ev.event_type}</span>
                            {ev.confirmed && <StatusChip status="ok" label="CONFIRMED" />}
                          </div>
                          <div className="text-[10px] text-text-muted font-mono mt-1">
                            @ {formatCurrency(ev.price_at)} &middot; {new Date(ev.ts).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })}
                          </div>
                        </div>
                      </div>
                    )) : <EmptyRow text="No structure events recorded yet" />}
                  </div>
                </div>

                {/* Bounce State Machine */}
                <div className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] p-4 sm:p-8">
                  <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-6 flex items-center gap-2">
                    <RotateCcw className="w-3 h-3 text-profit" /> Bounce State Machine
                  </h3>
                  <div className="space-y-3 max-h-[350px] overflow-y-auto pr-1">
                    {bounceEvents.length > 0 ? bounceEvents.map((be) => (
                      <div key={be.id} className="flex items-center gap-3 bg-cream-100/60 border-2 border-earth-700/10 rounded-[4px] px-3 sm:px-4 py-2.5 sm:py-3">
                        <BounceStateIcon state={be.state} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-black text-earth-700">{be.symbol}</span>
                            <span className="text-[10px] font-mono text-text-muted">{be.prev_state ? `${be.prev_state} →` : '→'} {be.state}</span>
                            {be.score != null && <ScoreBadge score={be.score} />}
                          </div>
                          <div className="text-[10px] text-text-muted font-mono mt-1">
                            {new Date(be.ts).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })}
                          </div>
                        </div>
                      </div>
                    )) : <EmptyRow text="Bounce catcher awaiting first capitulation signal" />}
                  </div>
                </div>
              </div>

              {/* Trade Intents (full width) */}
              <div className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] p-4 sm:p-8">
                <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-6 flex items-center gap-2">
                  <Target className="w-3 h-3 text-profit" /> Trade Intents
                </h3>
                <div className="space-y-3 max-h-[400px] overflow-y-auto pr-1">
                  {bounceIntents.length > 0 ? bounceIntents.map((intent) => (
                    <IntentRow key={intent.id} intent={intent} />
                  )) : <EmptyRow text="No trade intents emitted yet" />}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* ═══════════════ THOUGHTS SECTION ═══════════════ */}
      {activeSection === 'thoughts' && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <span className="text-xs text-text-muted">({filteredThoughts.length} entries)</span>
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-text-secondary" />
              <select
                value={filterType}
                onChange={e => setFilterType(e.target.value)}
                className="bg-cream-100 border-2 border-earth-700/10 rounded text-sm text-earth-700 px-2 py-1 outline-none focus:border-sakura-500"
                title="Filter by type"
              >
                <option value="all">All Types</option>
                {availableTypes.map(type => (
                  <option key={type} value={type}>{TYPE_CONFIG[type]?.label ?? type}</option>
                ))}
              </select>
            </div>
          </div>

          {thoughtsLoading ? (
            <div className="animate-pulse py-12 text-center text-text-muted text-xs">Consulting system memory...</div>
          ) : (
            <div className="space-y-3 max-w-3xl">
              {filteredThoughts.length > 0 ? filteredThoughts.map(thought => {
                const config = TYPE_CONFIG[thought.type] ?? TYPE_CONFIG.general;
                return (
                  <div key={thought.id} className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] p-4 flex gap-4">
                    <div className="flex-shrink-0 pt-1">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold uppercase ${config.bg} ${config.text}`}>
                        {thought.type[0].toUpperCase()}
                      </div>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-start mb-1 gap-2">
                        <div className="flex items-center gap-2 flex-wrap">
                          {thought.symbol && <span className="font-bold text-earth-700 text-sm">{thought.symbol}</span>}
                          <span className={`text-xs uppercase px-1.5 py-0.5 rounded border border-earth-700/10 font-bold ${config.text} ${config.bg}`}>
                            {config.label}
                          </span>
                        </div>
                        <span className="text-xs text-text-secondary whitespace-nowrap">{formatDate(thought.created_at)}</span>
                      </div>
                      <p className="text-text-primary text-sm leading-relaxed break-words">{thought.content}</p>
                    </div>
                  </div>
                );
              }) : (
                <div className="text-center py-12 text-text-muted">No thoughts found.</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// SUB-COMPONENTS
// ═══════════════════════════════════════════════════════════════════════

function KPIBlock({ icon: Icon, label, value, color }: { icon: typeof DollarSign; label: string; value: string; color: string }) {
  const colorMap: Record<string, string> = { profit: 'text-profit', loss: 'text-loss', warning: 'text-warning', white: 'text-earth-700' };
  const bgMap: Record<string, string> = { profit: 'bg-profit/10', loss: 'bg-loss/10', warning: 'bg-warning/10', white: 'bg-earth-700/5' };
  return (
    <div className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] p-3 sm:p-5 flex items-center gap-3 sm:gap-4">
      <div className={cn("w-8 sm:w-10 h-8 sm:h-10 rounded-[4px] flex items-center justify-center flex-shrink-0", bgMap[color] ?? 'bg-earth-700/5')}>
        <Icon className={cn("w-4 sm:w-5 h-4 sm:h-5", colorMap[color] ?? 'text-earth-700/40')} />
      </div>
      <div className="min-w-0">
        <div className="text-[9px] sm:text-[10px] font-black text-text-muted uppercase tracking-[0.15em]">{label}</div>
        <div className={cn("text-sm sm:text-lg font-black tracking-tight tabular-nums truncate", colorMap[color] ?? 'text-earth-700')}>{value}</div>
      </div>
    </div>
  );
}

function StatCard({ label, value, color, icon }: { label: string; value: number; color: string; icon: React.ReactNode }) {
  return (
    <div className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] p-4 flex items-center justify-between">
      <div>
        <div className="text-[10px] text-text-muted font-bold uppercase tracking-widest">{label}</div>
        <div className={cn('text-2xl font-black tabular-nums mt-1', color)}>{value}</div>
      </div>
      <div className={cn('opacity-40', color)}>{icon}</div>
    </div>
  );
}

function SummaryStat({ label, value, icon: Icon }: { label: string; value: number; icon: React.ComponentType<{ className?: string; size?: number }> }) {
  return (
    <div className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] p-4 flex items-center gap-3">
      <div className="w-8 h-8 rounded-full bg-cream-100/60 flex items-center justify-center">
        <Icon size={14} className="text-text-secondary" />
      </div>
      <div>
        <div className="text-lg font-black text-earth-700 font-mono">{value}</div>
        <div className="text-[10px] font-bold text-text-muted uppercase tracking-widest">{label}</div>
      </div>
    </div>
  );
}

function FilterBar({ label, items, active, onSelect }: { label: string; items: string[]; active: string; onSelect: (v: string) => void }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] font-black uppercase tracking-widest text-text-muted">{label}</span>
      <div className="flex flex-wrap gap-1">
        {items.map((s) => (
          <button
            key={s}
            onClick={() => onSelect(s)}
            className={cn(
              "px-2 sm:px-3 py-1.5 rounded-[4px] text-[9px] sm:text-[10px] font-black uppercase tracking-wider transition-all",
              active === s
                ? "bg-earth-700 text-cream-100"
                : "bg-cream-100/60 border-2 border-earth-700/10 text-text-muted hover:text-earth-700 hover:border-earth-700/20"
            )}
          >
            {s.replace('-USD', '')}
          </button>
        ))}
      </div>
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 70 ? "bg-profit/10 text-profit" : score >= 40 ? "bg-warning/10 text-warning" : "bg-loss/10 text-loss";
  return <span className={cn("text-[10px] font-black font-mono px-2 py-0.5 rounded-full", color)}>{score.toFixed(0)}</span>;
}

function EventIcon({ type }: { type: 'breakout' | 'breakdown' | 'retest' }) {
  const cls = "w-7 h-7 rounded-full flex items-center justify-center";
  switch (type) {
    case 'breakout': return <div className={cn(cls, "bg-profit/10")}><ArrowUpRight size={14} className="text-profit" /></div>;
    case 'breakdown': return <div className={cn(cls, "bg-loss/10")}><ArrowDownRight size={14} className="text-loss" /></div>;
    case 'retest': return <div className={cn(cls, "bg-warning/10")}><RotateCcw size={14} className="text-warning" /></div>;
  }
}

function BounceStateIcon({ state }: { state: string }) {
  const cls = "w-7 h-7 rounded-full flex items-center justify-center";
  switch (state.toLowerCase()) {
    case 'capitulation_detected': return <div className={cn(cls, "bg-loss/10")}><ArrowDownRight size={14} className="text-loss" /></div>;
    case 'stabilization_confirmed': return <div className={cn(cls, "bg-warning/10")}><ShieldCheck size={14} className="text-warning" /></div>;
    case 'idle': return <div className={cn(cls, "bg-surface-highlight")}><Minus size={14} className="text-text-muted" /></div>;
    default: return <div className={cn(cls, "bg-surface-highlight")}><CircleDot size={14} className="text-text-secondary" /></div>;
  }
}

function IntentRow({ intent }: { intent: BounceIntent }) {
  return (
    <div className="flex flex-wrap items-center gap-3 sm:gap-4 bg-cream-100/60 border-2 border-earth-700/10 rounded-[4px] px-3 sm:px-5 py-3 sm:py-4 text-xs">
      <div className="w-7 h-7 rounded-full flex items-center justify-center">
        {intent.blocked ? (
          <div className="w-7 h-7 rounded-full bg-loss/10 flex items-center justify-center"><ShieldX size={14} className="text-loss" /></div>
        ) : intent.executed ? (
          <div className="w-7 h-7 rounded-full bg-profit/10 flex items-center justify-center"><ShieldCheck size={14} className="text-profit" /></div>
        ) : (
          <div className="w-7 h-7 rounded-full bg-warning/10 flex items-center justify-center"><Target size={14} className="text-warning" /></div>
        )}
      </div>
      <div>
        <div className="flex items-center gap-2">
          <span className="font-black text-earth-700">{intent.symbol}</span>
          <span className="text-[10px] text-text-muted font-mono uppercase">{intent.entry_style}</span>
        </div>
        <div className="text-[10px] text-text-muted font-mono mt-0.5">
          {new Date(intent.ts).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })}
        </div>
      </div>
      <div className="text-right">
        <div className="text-[10px] text-text-muted uppercase tracking-wider">Entry</div>
        <div className="font-mono font-bold text-earth-700">{intent.entry_price ? formatCurrency(intent.entry_price) : '—'}</div>
      </div>
      <div className="text-right">
        <div className="text-[10px] text-text-muted uppercase tracking-wider">TP</div>
        <div className="font-mono font-bold text-profit">{intent.tp_price ? formatCurrency(intent.tp_price) : '—'}</div>
      </div>
      <div className="text-right">
        <div className="text-[10px] text-text-muted uppercase tracking-wider">SL</div>
        <div className="font-mono font-bold text-loss">{intent.sl_price ? formatCurrency(intent.sl_price) : '—'}</div>
      </div>
      <div className="flex flex-col items-end gap-1">
        {intent.score != null && <ScoreBadge score={intent.score} />}
        <span className={cn("text-[10px] font-black uppercase tracking-wider",
          intent.blocked ? "text-loss" : intent.executed ? "text-profit" : "text-warning"
        )}>
          {intent.blocked ? 'BLOCKED' : intent.executed ? 'EXECUTED' : 'PENDING'}
        </span>
      </div>
    </div>
  );
}

function EmptyRow({ text }: { text: string }) {
  return <div className="flex items-center justify-center py-8 text-text-muted/60 text-xs italic">{text}</div>;
}

function EmptyPanel({ icon: Icon, text, sub }: { icon: React.ComponentType<{ className?: string }>; text: string; sub: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-64 text-text-muted bg-paper-100/60 border-2 border-earth-700/10 rounded-[4px] space-y-4 col-span-full">
      <Icon className="w-8 h-8 opacity-20" />
      <div className="text-center">
        <p className="font-black text-earth-700 uppercase tracking-widest">{text}</p>
        <p className="text-[11px] font-medium text-text-muted mt-1 uppercase tracking-tighter italic">{sub}</p>
      </div>
    </div>
  );
}
