import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import type { Database } from '../lib/types';
import {
  Activity, TrendingUp, TrendingDown, Minus, Droplets, Gauge, BarChart3,
  ChevronDown, ChevronUp, Filter, ArrowUpDown, ShieldOff, Flame,
  Snowflake, AlertTriangle, Zap, Eye,
} from 'lucide-react';
import { supabase } from '../lib/supabaseClient';
import { MODE } from '../lib/mode';
import { cn } from '../lib/utils';
import IndicatorPanel from '../components/IndicatorPanel';
import {
  computeHeatScore, getTierStyle, heatSort,
  COMPONENT_LABELS,
  type HeatResult, type HeatTier,
} from '../lib/heatScore';

type CandidateScan = Database['public']['Tables']['candidate_scans']['Row'];

// ── Constants ──────────────────────────────────────────────────────────────

const STRATEGY_COLORS: Record<string, string> = {
  momentum_long: 'text-profit',
  trend_follow_long: 'text-blue-400',
  mean_reversion: 'text-yellow-400',
  mean_reversion_long: 'text-yellow-300',
  bb_mean_reversion_long: 'text-amber-400',
  bb_breakout_long: 'text-cyan-400',
  take_profit: 'text-orange-400',
  hold: 'text-text-muted',
};

const STRATEGY_LABELS: Record<string, string> = {
  momentum_long: 'Momentum Long',
  trend_follow_long: 'Trend Follow',
  mean_reversion: 'Mean Reversion',
  mean_reversion_long: 'MR Long',
  bb_mean_reversion_long: 'BB Mean Rev',
  bb_breakout_long: 'BB Breakout',
  take_profit: 'Take Profit',
  hold: 'Hold',
};

type SortMode = 'consensus' | 'bounce' | 'trend' | 'liquidity' | 'spread';
type FilterMode = 'all' | 'gold' | 'warm_plus' | 'hide_blocked';

const SORT_OPTIONS: { value: SortMode; label: string }[] = [
  { value: 'consensus', label: 'Consensus' },
  { value: 'bounce', label: 'Bounce / Confidence' },
  { value: 'trend', label: 'Trend Support' },
  { value: 'liquidity', label: 'Liquidity' },
  { value: 'spread', label: 'Spread (tightest)' },
];

const FILTER_OPTIONS: { value: FilterMode; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'gold', label: 'GOLD only' },
  { value: 'warm_plus', label: 'WARM+' },
  { value: 'hide_blocked', label: 'Hide BLOCKED' },
];

const TIER_ICON: Record<HeatTier, React.ReactNode> = {
  GOLD: <Flame className="w-3 h-3" />,
  WARM: <Zap className="w-3 h-3" />,
  COOL: <Eye className="w-3 h-3" />,
  COLD: <Snowflake className="w-3 h-3" />,
  BLOCKED: <ShieldOff className="w-3 h-3" />,
};

// ── Enriched type ──────────────────────────────────────────────────────────

interface EnrichedCandidate {
  scan: CandidateScan;
  heat: HeatResult;
}

// ── Component ──────────────────────────────────────────────────────────────

export default function Scanner() {
  const [candidates, setCandidates] = useState<CandidateScan[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortMode, setSortMode] = useState<SortMode>('consensus');
  const [filterMode, setFilterMode] = useState<FilterMode>('all');
  const [expandedSymbols, setExpandedSymbols] = useState<Set<string>>(new Set());

  // FLIP animation refs
  const containerRef = useRef<HTMLDivElement>(null);
  const positionsRef = useRef<Map<string, DOMRect>>(new Map());

  useEffect(() => {
    const fetchCandidates = async () => {
      try {
        if (candidates.length === 0) setLoading(true);

        const { data: latest } = await supabase
          .from('candidate_scans')
          .select('created_at')
          .eq('mode', MODE)
          .order('created_at', { ascending: false })
          .limit(1)
          .maybeSingle();

        if (!(latest as any)?.created_at) {
          setCandidates([]);
          return;
        }

        const { data, error } = await supabase
          .from('candidate_scans')
          .select('*')
          .eq('mode', MODE)
          .eq('created_at', (latest as any).created_at)
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

  // Compute heat scores for all candidates
  const enriched: EnrichedCandidate[] = useMemo(() => {
    return candidates.map(scan => ({
      scan,
      heat: computeHeatScore(
        scan.symbol,
        (scan.info as any) ?? {},
        (scan.score_breakdown as any) ?? {},
      ),
    }));
  }, [candidates]);

  // Apply sort + filter
  const sorted = useMemo(() => {
    let list = [...enriched];

    // Filter
    if (filterMode === 'gold') list = list.filter(e => e.heat.tier === 'GOLD');
    else if (filterMode === 'warm_plus') list = list.filter(e => e.heat.tier === 'GOLD' || e.heat.tier === 'WARM');
    else if (filterMode === 'hide_blocked') list = list.filter(e => e.heat.tier !== 'BLOCKED');

    // Sort
    if (sortMode === 'consensus') {
      list.sort((a, b) => heatSort(a.heat, b.heat));
    } else if (sortMode === 'bounce') {
      list.sort((a, b) => b.heat.score_components.bounce_prob - a.heat.score_components.bounce_prob);
    } else if (sortMode === 'trend') {
      list.sort((a, b) => b.heat.score_components.trend_support_proximity - a.heat.score_components.trend_support_proximity);
    } else if (sortMode === 'liquidity') {
      list.sort((a, b) => b.heat.score_components.liquidity_ok - a.heat.score_components.liquidity_ok);
    } else if (sortMode === 'spread') {
      const getSpread = (e: EnrichedCandidate) => ((e.scan.info as any)?.spread_pct ?? 999);
      list.sort((a, b) => getSpread(a) - getSpread(b));
    }

    return list;
  }, [enriched, sortMode, filterMode]);

  // FLIP: capture positions before DOM update
  const capturePositions = useCallback(() => {
    if (!containerRef.current) return;
    const cards = containerRef.current.querySelectorAll<HTMLElement>('[data-symbol]');
    const map = new Map<string, DOMRect>();
    cards.forEach(card => {
      const sym = card.dataset.symbol;
      if (sym) map.set(sym, card.getBoundingClientRect());
    });
    positionsRef.current = map;
  }, []);

  // FLIP: animate after DOM update
  useEffect(() => {
    if (!containerRef.current) return;
    const cards = containerRef.current.querySelectorAll<HTMLElement>('[data-symbol]');
    cards.forEach(card => {
      const sym = card.dataset.symbol;
      if (!sym) return;
      const prev = positionsRef.current.get(sym);
      if (!prev) return;
      const curr = card.getBoundingClientRect();
      const dx = prev.left - curr.left;
      const dy = prev.top - curr.top;
      if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return;
      card.style.transform = `translate(${dx}px, ${dy}px)`;
      card.style.transition = 'none';
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          card.style.transform = '';
          card.style.transition = 'transform 300ms cubic-bezier(0.25, 0.46, 0.45, 0.94)';
        });
      });
    });
  }, [sorted]);

  // Capture positions before each render that changes order
  useEffect(() => {
    capturePositions();
  }, [candidates, sortMode, filterMode]);

  const toggleExpand = (sym: string) => {
    setExpandedSymbols(prev => {
      const next = new Set(prev);
      if (next.has(sym)) next.delete(sym);
      else next.add(sym);
      return next;
    });
  };

  // Tier summary counts
  const tierCounts = useMemo(() => {
    const counts: Record<HeatTier, number> = { GOLD: 0, WARM: 0, COOL: 0, COLD: 0, BLOCKED: 0 };
    enriched.forEach(e => counts[e.heat.tier]++);
    return counts;
  }, [enriched]);

  if (loading) return <div className="text-text-secondary animate-pulse p-8">Scanning market...</div>;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-3 sm:gap-4 border-b border-border pb-4 sm:pb-8">
        <div>
          <h2 className="text-2xl sm:text-3xl font-black text-white tracking-tighter">Market Scanner</h2>
          <p className="text-xs sm:text-sm text-text-muted mt-1 sm:mt-2 font-medium tracking-tight">
            {candidates.length} symbols &middot; heat consensus
          </p>
          {/* Tier summary chips */}
          <div className="flex gap-2 mt-3 flex-wrap">
            {tierCounts.GOLD > 0 && (
              <span className="text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-400/30">
                {tierCounts.GOLD} Gold
              </span>
            )}
            {tierCounts.WARM > 0 && (
              <span className="text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400/80 border border-amber-500/20">
                {tierCounts.WARM} Warm
              </span>
            )}
            {tierCounts.COOL > 0 && (
              <span className="text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full bg-white/5 text-text-muted border border-white/10">
                {tierCounts.COOL} Cool
              </span>
            )}
            {tierCounts.COLD > 0 && (
              <span className="text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full bg-white/5 text-text-dim border border-white/8">
                {tierCounts.COLD} Cold
              </span>
            )}
            {tierCounts.BLOCKED > 0 && (
              <span className="text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full bg-red-500/15 text-red-400 border border-red-500/25">
                {tierCounts.BLOCKED} Blocked
              </span>
            )}
          </div>
        </div>
        <div className="flex flex-col items-end gap-3">
          <div className="bg-surface-highlight/50 px-4 py-2 rounded-xl border border-border text-[10px] font-black text-white uppercase tracking-[0.2em]">
            {candidates[0]?.created_at ? `Last scan: ${new Date(candidates[0].created_at).toLocaleTimeString()}` : 'Waiting...'}
          </div>
        </div>
      </div>

      {/* Controls: Sort + Filter */}
      <div className="flex flex-wrap gap-2 sm:gap-3">
        {/* Sort dropdown */}
        <div className="flex items-center gap-2">
          <ArrowUpDown className="w-3.5 h-3.5 text-text-muted hidden sm:block" />
          <select
            value={sortMode}
            onChange={e => setSortMode(e.target.value as SortMode)}
            className="bg-surface-base border border-border rounded-xl px-3 py-2 text-[11px] font-bold text-white focus:outline-none focus:border-amber-500/40 cursor-pointer appearance-none min-h-[40px]"
          >
            {SORT_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
        {/* Filter buttons */}
        <div className="flex items-center gap-1 sm:gap-1.5 flex-wrap">
          <Filter className="w-3.5 h-3.5 text-text-muted hidden sm:block" />
          {FILTER_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => setFilterMode(opt.value)}
              className={cn(
                'text-[10px] font-bold uppercase tracking-wider px-3 py-2 rounded-xl border transition-all duration-150 min-h-[40px]',
                filterMode === opt.value
                  ? 'bg-white/10 text-white border-white/20'
                  : 'bg-transparent text-text-muted border-border hover:text-white hover:border-white/15'
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Grid */}
      <div ref={containerRef} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
        {sorted.length > 0 ? sorted.map(({ scan: candidate, heat }) => (
          <ScannerCard
            key={candidate.symbol}
            candidate={candidate}
            heat={heat}
            expanded={expandedSymbols.has(candidate.symbol)}
            onToggleExpand={() => toggleExpand(candidate.symbol)}
          />
        )) : (
          <div className="col-span-full text-center py-20 text-text-muted italic border border-dashed border-border/50 rounded-cards bg-surface/50">
            <Activity className="w-8 h-8 text-border mx-auto mb-4 opacity-50" />
            {filterMode !== 'all'
              ? 'No symbols match the current filter.'
              : 'No scan candidates found. Scanner initializing...'}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Scanner Card ───────────────────────────────────────────────────────────

interface ScannerCardProps {
  candidate: CandidateScan;
  heat: HeatResult;
  expanded: boolean;
  onToggleExpand: () => void;
}

function ScannerCard({ candidate, heat, expanded, onToggleExpand }: ScannerCardProps) {
  const breakdown = (candidate.score_breakdown as any) ?? {};
  const info = (candidate.info as any) ?? {};
  const strategy = candidate.recommended_strategy ?? 'hold';
  const hasTechnicals = info.has_technicals ?? false;
  const style = getTierStyle(heat.score, heat.tier);

  return (
    <div
      data-symbol={candidate.symbol}
      className={cn(
        'relative overflow-hidden rounded-cards p-4 sm:p-7 group',
        'bg-surface-base transition-all duration-250',
        heat.tier === 'GOLD' && 'scanner-card-gold',
        heat.tier === 'BLOCKED' && 'scanner-card-blocked',
      )}
      style={{
        background: style.background !== 'none'
          ? `${style.background}, var(--color-surface-base)`
          : undefined,
        border: style.border,
        boxShadow: style.boxShadow,
        opacity: style.opacity,
      }}
    >
      {/* Decorative corner glow */}
      <div className={cn(
        'absolute top-0 right-0 w-32 h-32 rounded-full -mr-16 -mt-16 transition-all',
        heat.tier === 'GOLD' ? 'bg-amber-400/[0.06] group-hover:bg-amber-400/[0.10]' :
        heat.tier === 'WARM' ? 'bg-amber-400/[0.03] group-hover:bg-amber-400/[0.06]' :
        'bg-white/[0.02] group-hover:bg-white/[0.04]'
      )} />

      {/* Top row: Symbol + Badge | Score */}
      <div className="flex justify-between items-start mb-3 sm:mb-5 relative z-10">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-2xl sm:text-3xl font-black text-white tracking-tighter">{candidate.symbol}</h3>
            {/* Tier badge */}
            <span className={cn(
              'inline-flex items-center gap-1 text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full border',
              style.badgeClass,
            )}>
              {TIER_ICON[heat.tier]}
              {style.badgeLabel}
            </span>
          </div>
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
          <div className={cn(
            'text-3xl sm:text-4xl font-black tracking-tighter tabular-nums',
            heat.tier === 'GOLD' ? 'text-amber-300' :
            heat.tier === 'WARM' ? 'text-amber-400/90' :
            heat.tier === 'BLOCKED' ? 'text-red-400/70' :
            'text-white'
          )}>
            {heat.score}
          </div>
          <div className="text-[10px] text-text-muted font-black uppercase tracking-[0.2em] mt-1">/100</div>
        </div>
      </div>

      {/* Heat component mini-bars */}
      <div className="space-y-1.5 mb-5 relative z-10">
        {(Object.entries(COMPONENT_LABELS) as [keyof typeof COMPONENT_LABELS, { label: string; weight: number }][]).map(([key, { label, weight }]) => (
          <HeatBar
            key={key}
            label={label}
            value={heat.score_components[key]}
            weight={weight}
            tier={heat.tier}
          />
        ))}
      </div>

      {/* Original 4-Component Score Bars */}
      <div className="space-y-2 mb-5 relative z-10">
        <div className="text-[9px] font-black uppercase tracking-[0.2em] text-text-muted mb-1">Raw Score Breakdown</div>
        <ScoreBar label="Liquidity" value={breakdown.liquidity ?? 0} max={25} icon={<Droplets className="w-3 h-3" />} color="bg-blue-400" />
        <ScoreBar label="Momentum" value={breakdown.momentum ?? 0} max={30} icon={<TrendingUp className="w-3 h-3" />} color="bg-profit" />
        <ScoreBar label="Volatility" value={breakdown.volatility ?? 0} max={20} icon={<Gauge className="w-3 h-3" />} color="bg-yellow-400" />
        <ScoreBar label="Trend" value={breakdown.trend ?? 0} max={25} icon={<BarChart3 className="w-3 h-3" />} color="bg-white/80" />
      </div>

      {/* Blocked reasons inline */}
      {heat.tier === 'BLOCKED' && heat.gates_failed.length > 0 && (
        <div className="mb-4 relative z-10 space-y-1">
          <div className="flex items-center gap-1.5 text-[9px] font-black uppercase tracking-widest text-red-400">
            <AlertTriangle className="w-3 h-3" />
            Blocked
          </div>
          {heat.gates_failed.map((reason, i) => (
            <div key={i} className="text-[10px] text-red-400/80 font-medium pl-4">
              &bull; {reason}
            </div>
          ))}
        </div>
      )}

      {/* Chart Analysis: Patterns + MTF */}
      {(info.patterns?.length > 0 || info.mtf_alignment != null) && (
        <div className="mb-4 relative z-10">
          {info.mtf_alignment != null && (
            <div className="flex items-center gap-2 mb-2">
              {info.mtf_dominant_trend === 'bullish' ? (
                <TrendingUp className="w-3.5 h-3.5 text-profit" />
              ) : info.mtf_dominant_trend === 'bearish' ? (
                <TrendingDown className="w-3.5 h-3.5 text-loss" />
              ) : (
                <Minus className="w-3.5 h-3.5 text-text-muted" />
              )}
              <span className={cn(
                'text-[10px] font-black uppercase tracking-widest',
                info.mtf_alignment > 0.3 ? 'text-profit' : info.mtf_alignment < -0.3 ? 'text-loss' : 'text-yellow-400'
              )}>
                MTF {info.mtf_alignment > 0 ? '+' : ''}{info.mtf_alignment.toFixed(2)}
              </span>
            </div>
          )}
          {info.patterns?.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {(info.patterns as any[]).slice(0, 3).map((p: any, i: number) => (
                <span
                  key={`${p.name}-${i}`}
                  className={cn(
                    'text-[8px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border',
                    p.direction === 'bullish'
                      ? 'bg-profit/10 text-profit border-profit/20'
                      : p.direction === 'bearish'
                        ? 'bg-loss/10 text-loss border-loss/20'
                        : 'bg-yellow-400/10 text-yellow-400 border-yellow-400/20'
                  )}
                >
                  {p.name.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Advanced Indicators (MACD, BB, Consensus) */}
      {(info.macd || info.bollinger || info.consensus) && (
        <IndicatorPanel
          macd={info.macd}
          bollinger={info.bollinger}
          consensus={info.consensus}
          regime={info.regime}
          divergences={info.divergences}
          goldenDeathCross={info.golden_death_cross}
        />
      )}

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

      {/* Expand/collapse: "Why this tier" details */}
      <button
        onClick={onToggleExpand}
        className="w-full mt-4 flex items-center justify-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-text-muted hover:text-white transition-colors relative z-10 py-1"
      >
        {expanded ? 'Hide Details' : 'Why this score?'}
        {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      </button>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-border/40 relative z-10 space-y-2 scanner-detail-enter">
          <div className="text-[9px] font-black uppercase tracking-[0.2em] text-text-muted mb-2">
            {heat.tier === 'BLOCKED' ? 'Blocked because...' : `Why ${heat.tier}`}
          </div>
          {heat.gates_failed.length > 0 && (
            <div className="space-y-1 mb-3">
              {heat.gates_failed.map((reason, i) => (
                <div key={i} className="text-[10px] text-red-400 font-medium flex items-start gap-1.5">
                  <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
                  {reason}
                </div>
              ))}
            </div>
          )}
          {heat.reasons.map((reason, i) => (
            <div key={i} className="text-[10px] text-text-secondary font-medium flex items-start gap-1.5">
              <span className={cn(
                'w-1.5 h-1.5 rounded-full mt-1 shrink-0',
                heat.score_components[Object.keys(COMPONENT_LABELS)[i] as keyof typeof heat.score_components] > 0.6
                  ? 'bg-profit'
                  : heat.score_components[Object.keys(COMPONENT_LABELS)[i] as keyof typeof heat.score_components] > 0.35
                    ? 'bg-yellow-400'
                    : 'bg-red-400'
              )} />
              {reason}
            </div>
          ))}

          {/* View Chart Link */}
          <div className="pt-2">
            <Link
              to="/charts"
              className="text-[10px] text-text-muted hover:text-profit transition-colors font-bold uppercase tracking-widest"
            >
              View Chart &rarr;
            </Link>
          </div>
        </div>
      )}

      {/* Non-expanded chart link */}
      {!expanded && (
        <div className="pt-2 relative z-10">
          <Link
            to="/charts"
            className="text-[10px] text-text-muted hover:text-profit transition-colors font-bold uppercase tracking-widest"
          >
            View Chart &rarr;
          </Link>
        </div>
      )}
    </div>
  );
}

// ── Heat Bar (weighted component bar) ──────────────────────────────────────

function HeatBar({ label, value, weight, tier }: { label: string; value: number; weight: number; tier: HeatTier }) {
  const pct = Math.min(100, value * 100);
  const barColor = tier === 'BLOCKED' ? 'bg-red-400/40'
    : pct > 65 ? 'bg-amber-400'
    : pct > 40 ? 'bg-amber-400/60'
    : 'bg-white/20';

  return (
    <div className="flex items-center gap-2 text-[9px] font-bold uppercase tracking-wider">
      <span className="w-[80px] text-text-muted truncate">{label}</span>
      <div className="flex-1 h-1 bg-background/80 rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all duration-300', barColor)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-6 text-right text-text-secondary tabular-nums text-[8px]">{weight}%</span>
    </div>
  );
}

// ── Score Bar (original 4-component) ───────────────────────────────────────

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

// ── Indicator cell ─────────────────────────────────────────────────────────

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
