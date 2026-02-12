import { useState, useEffect, useMemo } from 'react';
import type { Database } from '../lib/types';
import { DataTable } from '../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import { cn, formatCurrency } from '../lib/utils';
import { Lock, FileEdit, CheckCircle, Target, Zap, ShieldCheck, DollarSign, TrendingUp } from 'lucide-react';
import { supabase } from '../lib/supabaseClient';
import { MODE } from '../lib/mode';
import { useDashboardData } from '../hooks/useDashboardData';

type PlanItem = Database['public']['Tables']['daily_gameplan_items']['Row'];
type CandidateScan = Database['public']['Tables']['candidate_scans']['Row'];

export default function Plan() {
  const [activeTab, setActiveTab] = useState<'draft' | 'refined' | 'locked'>('locked');
  const [planItems, setPlanItems] = useState<PlanItem[]>([]);
  const [candidates, setCandidates] = useState<CandidateScan[]>([]);
  const [loading, setLoading] = useState(true);
  const [source, setSource] = useState<'gameplan' | 'scanner'>('gameplan');

  const {
    cryptoCash,
    holdingsRows,
    healthSummary,
    dailyNotional,
    realizedPnl,
    recentEvents,
    loading: dashLoading,
  } = useDashboardData();

  useEffect(() => {
    const fetchPlan = async () => {
      try {
        setLoading(true);
        const today = new Date().toISOString().split('T')[0];

        // 1. Try the curated gameplan first
        const { data: plan, error: planError } = await supabase
          .from('daily_gameplans')
          .select('id, status')
          .eq('date', today)
          .maybeSingle();

        if (planError) {
          throw planError;
        }

        if (plan) {
          const planData = plan as any;
          setActiveTab(planData.status);
          setSource('gameplan');

          const { data: items, error: itemsError } = await supabase
            .from('daily_gameplan_items')
            .select('*')
            .eq('plan_id', planData.id);

          if (itemsError) throw itemsError;
          if (items) setPlanItems(items);
        } else {
          // 2. No curated plan — pull live scanner candidates
          setSource('scanner');
          setActiveTab('refined');

          const { data: scans, error: scanError } = await supabase
            .from('candidate_scans')
            .select('*')
            .eq('mode', MODE)
            .order('created_at', { ascending: false })
            .limit(12);

          if (scanError) throw scanError;
          if (scans) setCandidates(scans);
        }
      } catch (err) {
        console.error('Error fetching plan:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchPlan();
  }, []);

  // Derive "plan rows" from scanner candidates when no curated plan exists
  const scannerRows = useMemo(() => {
    return candidates
      .sort((a, b) => b.score - a.score)
      .map((c) => {
        const info = c.info as any;
        const breakdown = c.score_breakdown as any;
        return {
          symbol: c.symbol,
          score: c.score,
          strategy: c.recommended_strategy,
          catalyst: info?.catalyst && info.catalyst !== 'none' ? info.catalyst : null,
          regime: info?.sector ?? 'Crypto',
          ivr: info?.ivr ?? '—',
          trend: breakdown?.trend ?? 0,
          value: breakdown?.value ?? 0,
          volatility: breakdown?.volatility ?? 0,
          tier: c.score >= 40 ? 'Tier 1' : 'Tier 2',
          created_at: c.created_at,
        };
      });
  }, [candidates]);

  const cashAvailable = cryptoCash?.cash_available ?? 0;
  const buyingPower = cryptoCash?.buying_power ?? 0;
  const notionalUsed = dailyNotional?.notional_used ?? 0;

  // Curated gameplan columns
  const planColumns: ColumnDef<PlanItem>[] = [
    { header: 'Symbol', accessorKey: 'symbol', cell: i => <span className="font-black text-white tracking-widest">{i.getValue() as string}</span> },
    { header: 'Regime', accessorKey: 'regime' },
    { header: 'Preferred Action', accessorKey: 'preferred_strategy' },
    { header: 'Catalyst Signal', accessorKey: 'catalyst_summary' },
    {
      header: 'Risk Profile',
      accessorKey: 'risk_tier',
      cell: i => <span className={cn(
        "text-[10px] px-3 py-1 rounded-full border font-black uppercase tracking-widest",
        i.getValue() === 'Tier 1' ? "bg-profit/10 text-profit border-profit/20" : "bg-warning/10 text-warning border-warning/20"
      )}>{i.getValue() as string}</span>
    },
    { header: 'Intelligence Snapshot', accessorKey: 'ivr_tech_snapshot', cell: i => <span className="text-[11px] font-medium text-text-muted leading-relaxed italic">{i.getValue() as string}</span> }
  ];

  const isLoading = loading || dashLoading;

  return (
    <div className="space-y-10">
      {/* Header */}
      <div className="flex justify-between items-end border-b border-border pb-8">
        <div>
          <h2 className="text-3xl font-black text-white tracking-tighter">Autonomous Gameplan</h2>
          <p className="text-sm text-text-muted mt-2 font-medium tracking-tight">
            {source === 'gameplan'
              ? 'System-generated strategy for the current session.'
              : 'Live strategy derived from scanner intelligence.'}
          </p>
        </div>
        <div className="flex items-center gap-4">
          {source === 'scanner' && (
            <span className="text-[10px] font-black text-profit uppercase tracking-[0.2em] bg-profit/10 px-3 py-1.5 rounded-full border border-profit/20">
              Live Scanner
            </span>
          )}
          <div className="text-[10px] font-black text-text-muted uppercase tracking-[0.2em]">
            {new Date().toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
          </div>
        </div>
      </div>

      {/* KPI Strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card-premium p-5 flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-profit/10 flex items-center justify-center">
            <DollarSign className="w-5 h-5 text-profit" />
          </div>
          <div>
            <div className="text-[10px] font-black text-text-muted uppercase tracking-[0.15em]">Cash Available</div>
            <div className="text-lg font-black text-white tracking-tight tabular-nums">{formatCurrency(cashAvailable)}</div>
          </div>
        </div>
        <div className="card-premium p-5 flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center">
            <TrendingUp className="w-5 h-5 text-white/60" />
          </div>
          <div>
            <div className="text-[10px] font-black text-text-muted uppercase tracking-[0.15em]">Buying Power</div>
            <div className="text-lg font-black text-white tracking-tight tabular-nums">{formatCurrency(buyingPower)}</div>
          </div>
        </div>
        <div className="card-premium p-5 flex items-center gap-4">
          <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center", realizedPnl >= 0 ? "bg-profit/10" : "bg-loss/10")}>
            <DollarSign className={cn("w-5 h-5", realizedPnl >= 0 ? "text-profit" : "text-loss")} />
          </div>
          <div>
            <div className="text-[10px] font-black text-text-muted uppercase tracking-[0.15em]">Realized P&L</div>
            <div className={cn("text-lg font-black tracking-tight tabular-nums", realizedPnl >= 0 ? "text-profit" : "text-loss")}>
              {formatCurrency(realizedPnl)}
            </div>
          </div>
        </div>
        <div className="card-premium p-5 flex items-center gap-4">
          <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center", healthSummary.status === 'LIVE' ? "bg-profit/10" : "bg-warning/10")}>
            <ShieldCheck className={cn("w-5 h-5", healthSummary.status === 'LIVE' ? "text-profit" : "text-warning")} />
          </div>
          <div>
            <div className="text-[10px] font-black text-text-muted uppercase tracking-[0.15em]">System Status</div>
            <div className={cn("text-lg font-black tracking-tight", healthSummary.status === 'LIVE' ? "text-profit" : "text-warning")}>
              {healthSummary.status}
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-8 border-b border-border/50">
        {[
          { id: 'draft' as const, label: 'Draft', icon: FileEdit },
          { id: 'refined' as const, label: 'Refined', icon: CheckCircle },
          { id: 'locked' as const, label: 'Locked', icon: Lock }
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "pb-4 text-[10px] font-black uppercase tracking-[0.2em] flex items-center gap-2 border-b-2 transition-all duration-300",
              activeTab === tab.id ? "border-profit text-white" : "border-transparent text-text-muted hover:text-text-secondary"
            )}
          >
            <tab.icon className={cn("w-3.5 h-3.5", activeTab === tab.id ? "text-profit" : "")} /> {tab.label}
          </button>
        ))}
      </div>

      {/* Main Content */}
      <div className="min-h-[400px]">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center h-64 text-text-muted animate-pulse gap-4">
            <div className="w-12 h-12 border-2 border-border border-t-profit rounded-full animate-spin" />
            <span className="text-[10px] font-black uppercase tracking-widest italic">Interpreting market signals...</span>
          </div>
        ) : source === 'gameplan' && planItems.length > 0 ? (
          <DataTable columns={planColumns} data={planItems} />
        ) : source === 'scanner' && scannerRows.length > 0 ? (
          <div className="space-y-8">
            {/* Scanner-derived plan cards */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {scannerRows.map((row) => (
                <div key={row.symbol} className="card-premium p-6 group overflow-hidden relative">
                  <div className="absolute top-0 right-0 w-24 h-24 bg-white/[0.02] rounded-full -mr-12 -mt-12 transition-all group-hover:bg-white/[0.04]" />

                  {/* Symbol + Score header */}
                  <div className="flex justify-between items-start mb-5 relative z-10">
                    <div>
                      <h3 className="text-2xl font-black text-white tracking-tighter">{row.symbol}</h3>
                      <div className="flex gap-2 text-[10px] text-text-muted mt-1 font-black uppercase tracking-widest">
                        <span className="text-white/40">{row.regime}</span>
                        <span className="opacity-30">|</span>
                        <span className="text-white/40">IVR {row.ivr}</span>
                      </div>
                    </div>
                    <div className="flex flex-col items-end">
                      <div className="text-3xl font-black text-white tracking-tighter tabular-nums">{row.score}</div>
                      <div className="text-[9px] text-text-muted font-black uppercase tracking-[0.15em]">/100</div>
                    </div>
                  </div>

                  {/* Score breakdown bars */}
                  <div className="space-y-2 mb-5 relative z-10">
                    {[
                      { label: 'Trend', value: row.trend, max: 35, color: 'bg-white/70' },
                      { label: 'Value', value: row.value, max: 35, color: 'bg-profit' },
                      { label: 'Volatility', value: row.volatility, max: 35, color: 'bg-warning' },
                    ].map((bar) => (
                      <div key={bar.label} className="flex items-center gap-3 text-[10px] font-black uppercase tracking-widest">
                        <span className="w-20 text-text-muted">{bar.label}</span>
                        <div className="flex-1 h-1.5 bg-background rounded-full overflow-hidden">
                          <div className={cn("h-full rounded-full", bar.color)} style={{ width: `${(bar.value / bar.max) * 100}%` }} />
                        </div>
                        <span className="w-6 text-right text-text-muted tabular-nums">{bar.value}</span>
                      </div>
                    ))}
                  </div>

                  {/* Strategy + Risk */}
                  <div className="pt-4 border-t border-border/50 space-y-3 relative z-10">
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-text-muted font-black uppercase tracking-widest flex items-center gap-2">
                        <Target className="w-3 h-3 text-profit" /> Strategy
                      </span>
                      <span className="text-white font-black uppercase tracking-tight">{row.strategy}</span>
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

            {/* Holdings + Activity sidebar */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Current Holdings */}
              <div className="card-premium p-6">
                <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-5">
                  Current Holdings
                </h3>
                <div className="space-y-2">
                  {holdingsRows.length > 0 ? holdingsRows.map((h) => (
                    <div key={h.asset} className="flex justify-between items-center text-xs bg-background/50 border border-border rounded-lg px-4 py-2.5">
                      <span className="font-black text-white">{h.asset}</span>
                      <div className="flex gap-6">
                        <span className="font-mono text-text-secondary tabular-nums">{h.qty.toFixed(8)}</span>
                        <span className="font-mono text-text-muted tabular-nums w-14 text-right">{h.allocation.toFixed(1)}%</span>
                      </div>
                    </div>
                  )) : (
                    <div className="text-text-dim text-xs italic">No holdings snapshot available.</div>
                  )}
                </div>
              </div>

              {/* Recent Activity */}
              <div className="card-premium p-6">
                <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-5">
                  Recent Activity
                </h3>
                <div className="space-y-4 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
                  {recentEvents.length > 0 ? recentEvents.slice(0, 6).map((e, idx) => (
                    <div key={idx} className="flex gap-3 group">
                      <div className={cn(
                        "w-1 h-10 rounded-full transition-all group-hover:w-1.5",
                        e.type === 'TRADE' ? 'bg-profit' : 'bg-text-primary'
                      )} />
                      <div>
                        <p className="text-xs text-text-primary leading-relaxed">
                          <span className="font-black text-white">{e.symbol}</span> {e.details}
                        </p>
                        <p className="text-[10px] font-bold text-text-dim mt-0.5 tabular-nums uppercase">
                          {new Date(e.event_ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}
                        </p>
                      </div>
                    </div>
                  )) : (
                    <div className="text-text-dim text-xs italic">Awaiting first signal.</div>
                  )}
                </div>
              </div>
            </div>

            {/* Notional usage footer */}
            <div className="card-premium p-5 flex justify-between items-center">
              <div className="flex items-center gap-3">
                <ShieldCheck className="w-4 h-4 text-text-muted" />
                <span className="text-[10px] font-black text-text-muted uppercase tracking-[0.2em]">Daily Notional Used</span>
              </div>
              <span className="text-sm font-black text-white tabular-nums">{formatCurrency(notionalUsed)}</span>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-64 text-text-muted card-premium space-y-4 bg-surface/30">
            <Lock className="w-8 h-8 opacity-20" />
            <div className="text-center">
              <p className="font-black text-white uppercase tracking-widest">No Intelligence Record Found</p>
              <p className="text-[11px] font-medium text-text-muted mt-1 uppercase tracking-tighter italic">Zoe has not finalized the session strategy yet.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
