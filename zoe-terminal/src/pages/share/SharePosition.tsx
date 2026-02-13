import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ShareLayout } from '../../components/ShareLayout';
import { supabase } from '../../lib/supabaseClient';
import { Activity } from 'lucide-react';
import { formatCurrency, cn } from '../../lib/utils';

interface PositionDetail {
  id: string;
  symbol: string;
  strategy: string;
  direction: 'long' | 'short';
  entry_price: number;
  quantity: number;
  current_price: number;
  pnl_open: number;
  pnl_percent: number;
  status: string;
}

const SharePosition: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [position, setPosition] = useState<PositionDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPosition = async () => {
      if (!id) { setLoading(false); return; }

      const { data, error } = await supabase
        .from('positions')
        .select('*')
        .eq('id', id)
        .single();

      if (data && !error) {
        const d = data as any;
        const current_price = d.current_price ?? d.entry_price ?? 0;
        const entry = d.entry_price ?? 0;
        const qty = d.quantity ?? 0;
        const pnl_open = d.pnl_open ?? (
          d.direction === 'long'
            ? (current_price - entry) * qty * 100
            : (entry - current_price) * qty * 100
        );
        const costBasis = entry * qty * 100;
        const pnl_percent = costBasis !== 0 ? (pnl_open / costBasis) * 100 : 0;

        setPosition({
          ...d,
          current_price,
          pnl_open,
          pnl_percent,
        });
      }
      setLoading(false);
    };

    fetchPosition();
  }, [id]);

  if (loading) return <div className="p-8 text-earth-700">Loading position...</div>;
  if (!position) return <div className="p-8 text-earth-700">Position not found</div>;

  const isGreen = (position.pnl_open || 0) >= 0;

  return (
    <ShareLayout title="OPEN_MARKET_EXPOSURE">
      <div
        data-testid="position-ticket"
        className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] p-12 w-[1000px] flex flex-col gap-10 relative overflow-hidden"
      >
        {/* Header Section */}
        <div className="flex justify-between items-start relative z-10">
          <div className="flex items-center gap-8">
            <div className="w-20 h-20 bg-cream-100 border-2 border-earth-700/10 rounded-[4px] flex items-center justify-center">
              <Activity className="w-10 h-10 text-sakura-700" />
            </div>
            <div>
              <div className="flex items-center gap-4">
                <h2 className="text-6xl font-bold text-earth-700 tracking-tighter tabular-nums">{position.symbol}</h2>
                <span className={cn(
                  "text-[10px] px-3 py-1 rounded-[4px] border font-semibold uppercase tracking-[0.2em]",
                  position.direction === 'long' ? "bg-profit/10 text-profit border-profit/20" : "bg-loss/10 text-loss border-loss/20"
                )}>
                  {position.direction.toUpperCase()}
                </span>
              </div>
              <p className="text-text-muted font-semibold tracking-[0.2em] uppercase text-xs mt-2">Strategy: {position.strategy}</p>
            </div>
          </div>

          <div className="text-right">
            <div className={cn(
              "text-6xl font-bold tracking-tighter tabular-nums",
              isGreen ? 'text-profit' : 'text-loss'
            )}>
              {isGreen ? '+' : ''}{position.pnl_percent?.toFixed(2)}%
            </div>
            <div className={cn(
              "text-xl font-semibold tabular-nums mt-1",
              isGreen ? 'text-profit/60' : 'text-loss/60'
            )}>
              {isGreen ? '+' : ''}{formatCurrency(position.pnl_open || 0)}
            </div>
          </div>
        </div>

        <div className="h-px bg-earth-700/10 relative z-10" />

        {/* Body Section - Market Data */}
        <div className="grid grid-cols-2 gap-10 relative z-10">
          <div className="bg-cream-100/60 border-2 border-earth-700/10 rounded-[4px] p-8 flex flex-col gap-4">
            <div className="text-text-muted text-[10px] uppercase font-semibold tracking-[0.2em] mb-2">Entry Intelligence</div>
            <div className="flex justify-between items-center">
              <span className="text-text-dim text-xs font-semibold uppercase tracking-widest">Entry Benchmark</span>
              <span className="text-earth-700 font-semibold tabular-nums">{formatCurrency(position.entry_price)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-text-dim text-xs font-semibold uppercase tracking-widest">Quantity</span>
              <span className="text-earth-700 font-semibold tabular-nums">{position.quantity} Contracts</span>
            </div>
            <div className="pt-4 border-t border-earth-700/10 flex justify-between items-center">
              <span className="text-text-dim text-xs font-semibold uppercase tracking-widest">Cost Basis</span>
              <span className="text-earth-700 font-semibold tabular-nums">{formatCurrency(position.entry_price * position.quantity * 100)}</span>
            </div>
          </div>

          <div className="bg-cream-100/60 border-2 border-earth-700/10 rounded-[4px] p-8 flex flex-col gap-4">
            <div className="text-text-muted text-[10px] uppercase font-semibold tracking-[0.2em] mb-2">Market Dynamics</div>
            <div className="flex justify-between items-center">
              <span className="text-text-dim text-xs font-semibold uppercase tracking-widest">Current Mark</span>
              <span className="text-earth-700 font-semibold tabular-nums">{formatCurrency(position.current_price || 0)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-text-dim text-xs font-semibold uppercase tracking-widest">Notional Value</span>
              <span className="text-earth-700 font-semibold tabular-nums">{formatCurrency((position.current_price || 0) * position.quantity * 100)}</span>
            </div>
            <div className="pt-4 border-t border-earth-700/10 flex justify-between items-center">
              <span className="text-text-dim text-xs font-semibold uppercase tracking-widest">Status Code</span>
              <span className="text-profit font-semibold uppercase text-[10px] tracking-[0.2em]">ACTIVE_EXPOSURE</span>
            </div>
          </div>
        </div>

        {/* Footer Info */}
        <div className="flex justify-between items-center text-[10px] font-semibold text-text-dim uppercase tracking-[0.2em] bg-cream-100/60 px-6 py-4 rounded-[4px] border-2 border-earth-700/10 relative z-10">
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-3">
              <span className="text-earth-700/40">RISK_PROFILE</span>
              <span className="text-earth-700">DERIVATIVE_100X</span>
            </div>
            <div className="w-1 h-1 rounded-full bg-sakura-500/40" />
            <div className="flex items-center gap-3">
              <span className="text-earth-700/40">POSITION_ID</span>
              <span className="text-earth-700 font-mono">{position.id.slice(0, 12).toUpperCase()}</span>
            </div>
          </div>

          <div className="tracking-normal normal-case opacity-40">
            Market Intelligence Analytics
          </div>
        </div>
      </div>
    </ShareLayout>
  );
};

export default SharePosition;
