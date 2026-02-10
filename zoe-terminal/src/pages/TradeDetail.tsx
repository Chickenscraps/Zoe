import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Clock, Target, FileText, ExternalLink } from 'lucide-react';
import { StatusChip } from '../components/StatusChip';
import { formatCurrency, formatDate } from '../lib/utils';

// Mock data as fetching single trade from array is cleaner for demo
// Real impl would fetch from Supabase by ID
const MOCK_TRADE_DETAIL = {
  trade_id: 't1', 
  symbol: 'NVDA', 
  strategy: 'Short Put',
  status: 'closed',
  opened_at: '2023-09-15T10:00:00Z', 
  closed_at: '2023-09-20T14:30:00Z',
  realized_pnl: 150, 
  r_multiple: 0.5, 
  outcome: 'win', 
  rationale: 'Support hold at $400 level confirmed by volume.',
  entry_snapshot: {
      ivr: 45,
      rsi: 32,
      delta: 0.16,
      dte: 25,
      max_risk: 500,
      max_profit: 150
  },
  legs: [
      { type: 'put', strike: 400, qty: -1, entry: 1.50, exit: 0.05 }
  ],
  timeline: [
      { time: '2023-09-15T10:00:00Z', event: 'Entry', details: 'Sold 1 Put @ 1.50' },
      { time: '2023-09-18T14:00:00Z', event: 'Check', details: 'Price tested 405, held' },
      { time: '2023-09-20T14:30:00Z', event: 'Exit', details: 'Bought back @ 0.05 (TP Hit)' }
  ],
  artifacts: [
      { id: 'a1', name: 'chart_entry.png', url: '#' },
      { id: 'a2', name: 'analysis.md', url: '#' }
  ]
};

export default function TradeDetail() {
  const navigate = useNavigate();
  // const { trade, loading } = useTrade(id); // Implement hook later
  
  const trade = MOCK_TRADE_DETAIL; // Fallback

  if (!trade) return <div>Trade not found</div>;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <button 
        onClick={() => navigate(-1)}
        className="flex items-center text-sm text-text-secondary hover:text-white transition-colors"
      >
        <ArrowLeft className="w-4 h-4 mr-1" /> Back to Trades
      </button>

      {/* Header */}
      <div className="bg-surface border border-border rounded-lg p-6">
        <div className="flex justify-between items-start">
            <div>
                <div className="flex items-center gap-3 mb-2">
                    <h1 className="text-3xl font-bold text-white">{trade.symbol}</h1>
                    <StatusChip status={trade.outcome === 'win' ? 'ok' : trade.outcome === 'loss' ? 'error' : 'neutral'} label={trade.outcome.toUpperCase()} />
                </div>
                <div className="flex gap-4 text-sm text-text-secondary">
                    <span>{trade.strategy}</span>
                    <span>{formatDate(trade.opened_at)}</span>
                </div>
            </div>
            <div className="text-right">
                <div className={`text-3xl font-bold ${trade.realized_pnl >= 0 ? 'text-profit' : 'text-loss'}`}>
                    {formatCurrency(trade.realized_pnl)}
                </div>
                <div className="text-sm text-text-secondary">Realized P&L</div>
            </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Main Info */}
          <div className="md:col-span-2 space-y-6">
              {/* Legs Table */}
              <div className="bg-surface border border-border rounded-lg overflow-hidden">
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
                          {trade.legs.map((leg, i) => (
                              <tr key={i}>
                                  <td className="px-4 py-2 uppercase">{leg.type}</td>
                                  <td className="px-4 py-2">{leg.strike}</td>
                                  <td className="px-4 py-2">{leg.qty}</td>
                                  <td className="px-4 py-2">{formatCurrency(leg.entry)}</td>
                                  <td className="px-4 py-2">{formatCurrency(leg.exit)}</td>
                              </tr>
                          ))}
                      </tbody>
                  </table>
              </div>

              {/* Rationale */}
              <div className="bg-surface border border-border rounded-lg p-6">
                  <h3 className="font-medium text-sm text-text-secondary mb-3 flex items-center gap-2">
                      <FileText className="w-4 h-4" /> Rationale
                  </h3>
                  <p className="text-text-primary leading-relaxed">{trade.rationale}</p>
              </div>

               {/* Timeline */}
               <div className="bg-surface border border-border rounded-lg p-6">
                  <h3 className="font-medium text-sm text-text-secondary mb-4 flex items-center gap-2">
                      <Clock className="w-4 h-4" /> Timeline
                  </h3>
                  <div className="space-y-4">
                      {trade.timeline.map((event, i) => (
                          <div key={i} className="flex gap-4">
                              <div className="w-24 text-xs text-text-secondary shrink-0 pt-1">
                                  {formatDate(event.time).split(',')[1]}
                              </div>
                              <div className="flex-1 pb-4 border-l border-border pl-4 relative">
                                  <div className="absolute w-2 h-2 bg-text-secondary rounded-full -left-[5px] top-1.5" />
                                  <p className="text-sm font-medium text-white">{event.event}</p>
                                  <p className="text-sm text-text-muted">{event.details}</p>
                              </div>
                          </div>
                      ))}
                  </div>
              </div>
          </div>

          {/* Sidebar Stats */}
          <div className="space-y-6">
              <div className="bg-surface border border-border rounded-lg p-4">
                  <h3 className="font-medium text-sm text-text-secondary mb-4 flex items-center gap-2">
                      <Target className="w-4 h-4" /> Entry Snapshot
                  </h3>
                  <div className="space-y-3">
                      <div className="flex justify-between text-sm">
                          <span className="text-text-muted">IVR</span>
                          <span className="text-white font-mono">{trade.entry_snapshot.ivr}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                          <span className="text-text-muted">RSI</span>
                          <span className="text-white font-mono">{trade.entry_snapshot.rsi}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                          <span className="text-text-muted">Delta</span>
                          <span className="text-white font-mono">{trade.entry_snapshot.delta}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                          <span className="text-text-muted">DTE</span>
                          <span className="text-white font-mono">{trade.entry_snapshot.dte}</span>
                      </div>
                      <div className="pt-2 border-t border-border mt-2">
                           <div className="flex justify-between text-sm">
                              <span className="text-text-muted">Max Risk</span>
                              <span className="text-white font-mono">{formatCurrency(trade.entry_snapshot.max_risk)}</span>
                          </div>
                           <div className="flex justify-between text-sm">
                              <span className="text-text-muted">Max Profit</span>
                              <span className="text-white font-mono">{formatCurrency(trade.entry_snapshot.max_profit)}</span>
                          </div>
                      </div>
                  </div>
              </div>

              {/* Evidence */}
              <div className="bg-surface border border-border rounded-lg p-4">
                  <h3 className="font-medium text-sm text-text-secondary mb-4">Evidence</h3>
                  <div className="space-y-2">
                      {trade.artifacts.map(art => (
                          <div key={art.id} className="flex items-center gap-2 text-sm p-2 bg-surface-highlight/30 rounded hover:bg-surface-highlight/50 cursor-pointer transition-colors">
                              <ExternalLink className="w-3 h-3 text-text-muted" />
                              <span className="text-blue-400 hover:underline truncate">{art.name}</span>
                          </div>
                      ))}
                  </div>
              </div>
          </div>
      </div>
    </div>
  );
}
