import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ShareLayout } from '../../components/ShareLayout';
import { StatusChip } from '../../components/StatusChip';
import { formatCurrency, formatDate, cn } from '../../lib/utils';
import { Target, Clock, TrendingUp, Zap } from 'lucide-react';
import { supabase } from '../../lib/supabaseClient';

interface TradeData {
  symbol: string;
  strategy: string;
  status: string;
  opened_at: string;
  closed_at?: string;
  realized_pnl: number;
  outcome: string;
  entry_snapshot: {
    ivr?: number;
    delta?: number;
    dte?: number;
    max_risk?: number;
  };
  legs: Array<{
    type: string;
    strike: number;
    qty: number;
    price: number;
  }>;
}

export default function ShareTrade() {
  const { id } = useParams<{ id: string }>();
  const [trade, setTrade] = useState<TradeData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchTrade() {
      if (!id) { setLoading(false); return; }
      try {
        const { data, error } = await supabase
          .from('trades')
          .select('*')
          .eq('trade_id', id)
          .single();

        if (error) throw error;
        if (data) {
          const d = data as any;
          setTrade({
            symbol: d.symbol ?? '',
            strategy: d.strategy ?? '',
            status: d.status ?? 'closed',
            opened_at: d.opened_at ?? d.created_at ?? '',
            closed_at: d.closed_at,
            realized_pnl: d.realized_pnl ?? 0,
            outcome: d.outcome ?? '',
            entry_snapshot: d.entry_snapshot ?? {},
            legs: d.legs ?? [],
          });
        }
      } catch (err) {
        console.error('Error fetching trade:', err);
      } finally {
        setLoading(false);
      }
    }
    fetchTrade();
  }, [id]);

  if (loading) return <div className="p-8 text-white">Loading trade...</div>;
  if (!trade) return <div className="p-8 text-white">Trade not found</div>;

  const pnlPositive = trade.realized_pnl >= 0;

  return (
    <ShareLayout title="TRADE_EXECUTION_SETTLED">
      <div
        data-testid="trade-ticket"
        className="card-premium p-12 w-[1000px] flex flex-col gap-10 relative overflow-hidden"
      >
        {/* Top Header */}
        <div className="flex justify-between items-start relative z-10">
          <div className="flex items-center gap-8">
            <div className="w-20 h-20 bg-background border border-border rounded-2xl flex items-center justify-center shadow-crisp">
              <TrendingUp className="w-10 h-10 text-profit" />
            </div>
            <div>
              <div className="flex items-center gap-4">
                <h2 className="text-6xl font-bold text-white tracking-tighter tabular-nums">{trade.symbol}</h2>
                <StatusChip status="ok" label="SETTLED" />
              </div>
              <p className="text-text-muted font-semibold tracking-[0.2em] uppercase text-xs mt-2">{trade.strategy}</p>
            </div>
          </div>

          <div className="text-right">
            <div className={`text-6xl font-bold tracking-tighter tabular-nums ${pnlPositive ? 'text-profit' : 'text-loss'}`}>
              {pnlPositive ? '+' : ''}{formatCurrency(trade.realized_pnl)}
            </div>
            <p className="text-text-dim font-semibold uppercase tracking-[0.2em] text-[10px] mt-2">Realized Net Yield</p>
          </div>
        </div>

        <div className="h-px bg-border/50 relative z-10" />

        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-8 relative z-10">
          <div className="bg-background/50 border border-border rounded-2xl p-6">
            <div className="flex items-center gap-2 text-text-muted text-[10px] uppercase font-semibold tracking-[0.2em] mb-3">
              <Zap className="w-3.5 h-3.5 text-profit" /> Vol / IVR
            </div>
            <div className="text-2xl font-bold text-white tabular-nums">{trade.entry_snapshot.ivr ?? '--'}</div>
          </div>
          <div className="bg-background/50 border border-border rounded-2xl p-6">
            <div className="flex items-center gap-2 text-text-muted text-[10px] uppercase font-semibold tracking-[0.2em] mb-3">
              <Target className="w-3.5 h-3.5" /> Delta Exp
            </div>
            <div className="text-2xl font-bold text-white tabular-nums">{trade.entry_snapshot.delta ?? '--'}</div>
          </div>
          <div className="bg-background/50 border border-border rounded-2xl p-6">
            <div className="flex items-center gap-2 text-text-muted text-[10px] uppercase font-semibold tracking-[0.2em] mb-3">
              <Clock className="w-3.5 h-3.5" /> Duration
            </div>
            <div className="text-2xl font-bold text-white tabular-nums">{trade.entry_snapshot.dte ?? '--'} DTE</div>
          </div>
          <div className="bg-background/50 border border-border rounded-2xl p-6">
            <div className="text-text-muted text-[10px] uppercase font-semibold tracking-[0.2em] mb-3 text-loss">Collateral</div>
            <div className="text-2xl font-bold text-white tabular-nums">{formatCurrency(trade.entry_snapshot.max_risk ?? 0)}</div>
          </div>
        </div>

        {/* Leg Summary */}
        {trade.legs.length > 0 && (
        <div className="bg-background/30 rounded-2xl p-8 border border-border relative z-10">
          <div className="text-[10px] text-text-muted uppercase font-semibold tracking-[0.3em] mb-6">Component Breakdown</div>
          <div className="grid grid-cols-2 gap-x-16 gap-y-4">
            {trade.legs.map((leg, i) => (
              <div key={i} className="flex justify-between items-center text-xs">
                <span className="text-white font-semibold tracking-tight flex items-center gap-3">
                  <div className={cn(
                    "w-1.5 h-1.5 rounded-full",
                    leg.type === 'call' ? 'bg-white opacity-40' : 'bg-profit'
                  )} />
                  {Math.abs(leg.qty)}x {leg.strike} {leg.type.toUpperCase()}
                </span>
                <span className="font-semibold text-text-muted tabular-nums uppercase tracking-widest">{formatCurrency(leg.price)}</span>
              </div>
            ))}
          </div>
        </div>
        )}

        {/* Timeline */}
        <div className="flex justify-between items-center text-[10px] font-semibold text-text-dim uppercase tracking-[0.2em] bg-background/50 px-6 py-4 rounded-xl border border-border relative z-10">
          <span>Executed: {trade.opened_at ? formatDate(trade.opened_at) : '--'}</span>
          <div className="w-1 h-1 rounded-full bg-border" />
          <span>Settled: {trade.closed_at ? formatDate(trade.closed_at) : formatDate(new Date().toISOString())}</span>
        </div>
      </div>
    </ShareLayout>
  );
}
