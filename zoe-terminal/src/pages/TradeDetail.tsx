import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Clock, Target, FileText, ExternalLink } from 'lucide-react';
import { StatusChip } from '../components/StatusChip';
import { formatCurrency, formatDate } from '../lib/utils';
import { useEffect, useState } from 'react';
import { supabase } from '../lib/supabaseClient';


interface TradeDetailData {
  trade_id: string;
  symbol: string;
  strategy: string;
  status: string;
  opened_at: string;
  closed_at: string | null;
  realized_pnl: number;
  r_multiple: number | null;
  outcome: string;
  rationale: string | null;
  entry_snapshot: Record<string, any> | null;
  legs: Array<Record<string, any>>;
  timeline: Array<Record<string, any>>;
  artifacts: Array<Record<string, any>>;
}

export default function TradeDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [trade, setTrade] = useState<TradeDetailData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchTrade() {
      if (!id) return;
      try {
        setLoading(true);
        const { data, error } = await supabase
          .from('trades')
          .select('*')
          .eq('trade_id', id)
          .single();

        if (error) throw error;
        if (data) {
          const d = data as any;
          setTrade({
            trade_id: d.trade_id,
            symbol: d.symbol,
            strategy: d.strategy ?? '',
            status: d.status ?? 'closed',
            opened_at: d.opened_at,
            closed_at: d.closed_at,
            realized_pnl: d.realized_pnl ?? 0,
            r_multiple: d.r_multiple,
            outcome: d.outcome ?? 'neutral',
            rationale: d.rationale,
            entry_snapshot: d.entry_snapshot ?? {},
            legs: Array.isArray(d.legs) ? d.legs : [],
            timeline: Array.isArray(d.timeline) ? d.timeline : [],
            artifacts: Array.isArray(d.artifacts) ? d.artifacts : [],
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

  if (loading) {
    return <div className="text-text-secondary animate-pulse p-8">Loading trade...</div>;
  }

  if (!trade) {
    return (
      <div className="space-y-6 max-w-5xl mx-auto">
        <button onClick={() => navigate(-1)} className="flex items-center text-sm text-text-secondary hover:text-text-primary transition-colors">
          <ArrowLeft className="w-4 h-4 mr-1" /> Back to Trades
        </button>
        <div className="bg-surface-base border-2 border-earth-700/20 rounded-[4px] shadow-soft p-12 text-center text-text-muted">Trade not found.</div>
      </div>
    );
  }

  const snap = trade.entry_snapshot ?? {};

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <button
        onClick={() => navigate(-1)}
        className="flex items-center text-sm text-text-secondary hover:text-text-primary transition-colors"
      >
        <ArrowLeft className="w-4 h-4 mr-1" /> Back to Trades
      </button>

      {/* Header */}
      <div className="bg-surface border border-border rounded-[4px] p-6">
        <div className="flex justify-between items-start min-w-0">
            <div>
                <div className="flex items-center gap-3 mb-2">
                    <h1 className="text-3xl font-semibold text-text-primary">{trade.symbol}</h1>
                    <StatusChip status={trade.outcome === 'win' ? 'ok' : trade.outcome === 'loss' ? 'error' : 'neutral'} label={trade.outcome.toUpperCase()} />
                </div>
                <div className="flex gap-4 text-sm text-text-secondary">
                    <span>{trade.strategy}</span>
                    <span>{formatDate(trade.opened_at)}</span>
                </div>
            </div>
            <div className="text-right">
                <div className={`text-3xl font-semibold ${trade.realized_pnl >= 0 ? 'text-profit' : 'text-loss'}`}>
                    {formatCurrency(trade.realized_pnl)}
                </div>
                <div className="text-sm text-text-secondary">Realized P&L</div>
            </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-2 space-y-6">
              {trade.legs.length > 0 && (
              <div className="bg-surface border border-border rounded-[4px] overflow-hidden">
                  <div className="px-4 py-3 border-b border-border bg-surface-highlight/50">
                      <h3 className="font-medium text-sm">Legs</h3>
                  </div>
                  <table className="w-full text-sm text-left">
                      <thead className="text-xs text-text-secondary uppercase bg-surface-highlight/20">
                          <tr>
                              <th className="px-4 py-2">Type</th>
                              <th className="px-4 py-2">Strike</th>
                              <th className="px-4 py-2">Qty</th>
                              <th className="px-4 py-2">Entry</th>
                              <th className="px-4 py-2">Exit</th>
                          </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                          {trade.legs.map((leg: any, i: number) => (
                              <tr key={i}>
                                  <td className="px-4 py-2 uppercase">{leg.type}</td>
                                  <td className="px-4 py-2">{leg.strike}</td>
                                  <td className="px-4 py-2">{leg.qty}</td>
                                  <td className="px-4 py-2">{formatCurrency(leg.entry ?? leg.price ?? 0)}</td>
                                  <td className="px-4 py-2">{leg.exit != null ? formatCurrency(leg.exit) : '-'}</td>
                              </tr>
                          ))}
                      </tbody>
                  </table>
              </div>
              )}

              {trade.rationale && (
              <div className="bg-surface border border-border rounded-[4px] p-6">
                  <h3 className="font-medium text-sm text-text-secondary mb-3 flex items-center gap-2">
                      <FileText className="w-4 h-4" /> Rationale
                  </h3>
                  <p className="text-text-primary leading-relaxed">{trade.rationale}</p>
              </div>
              )}

               {trade.timeline.length > 0 && (
               <div className="bg-surface border border-border rounded-[4px] p-6">
                  <h3 className="font-medium text-sm text-text-secondary mb-4 flex items-center gap-2">
                      <Clock className="w-4 h-4" /> Timeline
                  </h3>
                  <div className="space-y-4">
                      {trade.timeline.map((event: any, i: number) => (
                          <div key={i} className="flex gap-4">
                              <div className="w-24 text-xs text-text-secondary shrink-0 pt-1">
                                  {event.time ? formatDate(event.time).split(',')[1] : ''}
                              </div>
                              <div className="flex-1 pb-4 border-l border-border pl-4 relative">
                                  <div className="absolute w-2 h-2 bg-text-secondary rounded-full -left-[5px] top-1.5" />
                                  <p className="text-sm font-medium text-text-primary">{event.event}</p>
                                  <p className="text-sm text-text-muted">{event.details}</p>
                              </div>
                          </div>
                      ))}
                  </div>
              </div>
              )}
          </div>

          <div className="space-y-6">
              {Object.keys(snap).length > 0 && (
              <div className="bg-surface border border-border rounded-[4px] p-4">
                  <h3 className="font-medium text-sm text-text-secondary mb-4 flex items-center gap-2">
                      <Target className="w-4 h-4" /> Entry Snapshot
                  </h3>
                  <div className="space-y-3">
                      {snap.ivr != null && <div className="flex justify-between text-sm"><span className="text-text-muted">IVR</span><span className="text-text-primary font-mono">{snap.ivr}</span></div>}
                      {snap.rsi != null && <div className="flex justify-between text-sm"><span className="text-text-muted">RSI</span><span className="text-text-primary font-mono">{snap.rsi}</span></div>}
                      {snap.delta != null && <div className="flex justify-between text-sm"><span className="text-text-muted">Delta</span><span className="text-text-primary font-mono">{snap.delta}</span></div>}
                      {snap.dte != null && <div className="flex justify-between text-sm"><span className="text-text-muted">DTE</span><span className="text-text-primary font-mono">{snap.dte}</span></div>}
                      {(snap.max_risk != null || snap.max_profit != null) && (
                      <div className="pt-2 border-t border-border mt-2">
                           {snap.max_risk != null && <div className="flex justify-between text-sm"><span className="text-text-muted">Max Risk</span><span className="text-text-primary font-mono">{formatCurrency(snap.max_risk)}</span></div>}
                           {snap.max_profit != null && <div className="flex justify-between text-sm"><span className="text-text-muted">Max Profit</span><span className="text-text-primary font-mono">{formatCurrency(snap.max_profit)}</span></div>}
                      </div>
                      )}
                  </div>
              </div>
              )}

              {trade.artifacts.length > 0 && (
              <div className="bg-surface border border-border rounded-[4px] p-4">
                  <h3 className="font-medium text-sm text-text-secondary mb-4">Evidence</h3>
                  <div className="space-y-2">
                      {trade.artifacts.map((art: any, i: number) => (
                          <div key={art.id ?? i} className="flex items-center gap-2 text-sm p-2 bg-surface-highlight/30 rounded hover:bg-surface-highlight/50 cursor-pointer transition-colors">
                              <ExternalLink className="w-3 h-3 text-text-muted" />
                              <span className="text-blue-400 hover:underline truncate">{art.name}</span>
                          </div>
                      ))}
                  </div>
              </div>
              )}
          </div>
      </div>
    </div>
  );
}
