import { useParams } from 'react-router-dom';
import { ShareLayout } from '../../components/ShareLayout';
import { StatusChip } from '../../components/StatusChip';
import { formatCurrency, formatDate } from '../../lib/utils';
import { Target, Clock, TrendingUp, Zap } from 'lucide-react';

export default function ShareTrade() {
  const { id } = useParams();

  // In a real app, this would use a useTrade hook with the ID
  // For the renderer, we'll use mock data if ID starts with mock
  const trade = {
    symbol: 'SPY',
    strategy: 'Iron Condor',
    status: 'closed',
    opened_at: new Date().toISOString(),
    realized_pnl: 245.00,
    outcome: 'win',
    entry_snapshot: {
      ivr: 32,
      delta: 0.12,
      dte: 45,
      max_risk: 1200
    },
    legs: [
      { type: 'call', strike: 510, qty: -1, price: 2.10 },
      { type: 'call', strike: 515, qty: 1, price: 0.85 },
      { type: 'put', strike: 480, qty: -1, price: 1.95 },
      { type: 'put', strike: 475, qty: 1, price: 0.70 }
    ]
  };

  return (
    <ShareLayout title="TRADE_TICKET_SETTLEMENT">
      <div 
        data-testid="trade-ticket"
        className="bg-surface/80 backdrop-blur-md border border-white/10 rounded-2xl shadow-2xl p-8 w-[900px] flex flex-col gap-6"
      >
        {/* Top Header */}
        <div className="flex justify-between items-start">
          <div className="flex items-center gap-6">
            <div className="bg-brand/10 p-4 rounded-xl border border-brand/20">
              <TrendingUp className="w-8 h-8 text-brand" />
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-5xl font-black text-white tracking-tighter">{trade.symbol}</h2>
                <StatusChip status="ok" label="SETTLED" />
              </div>
              <p className="text-text-secondary font-medium tracking-wide uppercase text-sm mt-1">{trade.strategy}</p>
            </div>
          </div>
          
          <div className="text-right">
            <div className="text-5xl font-black text-profit tracking-tighter">
              +{formatCurrency(trade.realized_pnl)}
            </div>
            <p className="text-text-secondary font-mono text-xs uppercase tracking-widest mt-1">Realized Profit</p>
          </div>
        </div>

        <div className="h-px bg-white/5" />

        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-6">
          <div className="bg-white/5 rounded-xl p-4 border border-white/5">
            <div className="flex items-center gap-2 text-text-muted text-[10px] uppercase font-bold tracking-widest mb-1">
              <Zap className="w-3 h-3" /> IVR
            </div>
            <div className="text-xl font-mono text-white">{trade.entry_snapshot.ivr}</div>
          </div>
          <div className="bg-white/5 rounded-xl p-4 border border-white/5">
            <div className="flex items-center gap-2 text-text-muted text-[10px] uppercase font-bold tracking-widest mb-1">
              <Target className="w-3 h-3" /> Delta
            </div>
            <div className="text-xl font-mono text-white">{trade.entry_snapshot.delta}</div>
          </div>
          <div className="bg-white/5 rounded-xl p-4 border border-white/5">
            <div className="flex items-center gap-2 text-text-muted text-[10px] uppercase font-bold tracking-widest mb-1">
              <Clock className="w-3 h-3" /> DTE
            </div>
            <div className="text-xl font-mono text-white">{trade.entry_snapshot.dte}</div>
          </div>
          <div className="bg-white/5 rounded-xl p-4 border border-white/5">
            <div className="text-text-muted text-[10px] uppercase font-bold tracking-widest mb-1">Max Risk</div>
            <div className="text-xl font-mono text-white">{formatCurrency(trade.entry_snapshot.max_risk)}</div>
          </div>
        </div>

        {/* Leg Summary (Condensed) */}
        <div className="bg-black/20 rounded-xl p-4 border border-white/5">
          <div className="text-[10px] text-text-muted uppercase font-bold tracking-widest mb-3">Leg Summary</div>
          <div className="grid grid-cols-2 gap-x-12 gap-y-2">
            {trade.legs.map((leg, i) => (
              <div key={i} className="flex justify-between items-center text-xs">
                <span className="text-text-secondary flex gap-2">
                  <span className={`w-1 h-3 rounded-full ${leg.type === 'call' ? 'bg-brand' : 'bg-blue-500'}`} />
                  {Math.abs(leg.qty)}x {leg.strike} {leg.type.toUpperCase()}
                </span>
                <span className="font-mono text-white">{formatCurrency(leg.price)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="flex justify-between items-center text-[10px] text-text-muted font-mono bg-white/5 px-4 py-2 rounded-lg border border-white/5">
          <span>OPENED: {formatDate(trade.opened_at)}</span>
          <span>CLOSED: {formatDate(new Date().toISOString())}</span>
        </div>
      </div>
    </ShareLayout>
  );
}
