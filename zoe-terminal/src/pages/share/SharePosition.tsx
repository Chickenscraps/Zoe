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
  current_price?: number;
  pnl_open?: number;
  pnl_percent?: number;
  status: string;
}

const SharePosition: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [position, setPosition] = useState<PositionDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPosition = async () => {
      if (!id) return;
      
      const { data, error } = await supabase
        .from('positions')
        .select('*')
        .eq('id', id)
        .single();

      if (data && !error) {
        const d = data as any;
        // Mock current price for screenshot if not available
        const current_price = d.current_price || d.entry_price * (1 + (Math.random() * 0.1 - 0.05));
        const pnl_open = d.direction === 'long' 
          ? (current_price - d.entry_price) * d.quantity * 100
          : (d.entry_price - current_price) * d.quantity * 100;
        const pnl_percent = (pnl_open / (d.entry_price * d.quantity * 100)) * 100;

        setPosition({
          ...d,
          current_price,
          pnl_open,
          pnl_percent
        });
      }
      setLoading(false);
    };

    fetchPosition();
  }, [id]);

  if (loading) return <div className="p-8 text-white">Loading position...</div>;
  if (!position) return <div className="p-8 text-white">Position not found</div>;

  const isGreen = (position.pnl_open || 0) >= 0;

  return (
    <ShareLayout title="OPEN_MARKET_EXPOSURE">
      <div 
        data-testid="position-ticket" 
        className="card-premium p-12 w-[1000px] flex flex-col gap-10 relative overflow-hidden"
      >
        {/* Header Section */}
        <div className="flex justify-between items-start relative z-10">
          <div className="flex items-center gap-8">
            <div className="w-20 h-20 bg-background border border-border rounded-2xl flex items-center justify-center shadow-crisp">
              <Activity className="w-10 h-10 text-white opacity-40" />
            </div>
            <div>
              <div className="flex items-center gap-4">
                <h2 className="text-6xl font-black text-white tracking-tighter tabular-nums">{position.symbol}</h2>
                <span className={cn(
                  "text-[10px] px-3 py-1 rounded-full border font-black uppercase tracking-[0.2em]",
                  position.direction === 'long' ? "bg-profit/10 text-profit border-profit/20" : "bg-loss/10 text-loss border-loss/20"
                )}>
                  {position.direction.toUpperCase()}
                </span>
              </div>
              <p className="text-text-muted font-black tracking-[0.2em] uppercase text-xs mt-2">Strategy: {position.strategy}</p>
            </div>
          </div>
          
          <div className="text-right">
            <div className={cn(
              "text-6xl font-black tracking-tighter tabular-nums",
              isGreen ? 'text-profit' : 'text-loss'
            )}>
              {isGreen ? '+' : ''}{position.pnl_percent?.toFixed(2)}%
            </div>
            <div className={cn(
              "text-xl font-black tabular-nums mt-1",
              isGreen ? 'text-profit/60' : 'text-loss/60'
            )}>
              {isGreen ? '+' : ''}{formatCurrency(position.pnl_open || 0)}
            </div>
          </div>
        </div>

        <div className="h-px bg-border/50 relative z-10" />

        {/* Body Section - Market Data */}
        <div className="grid grid-cols-2 gap-10 relative z-10">
          <div className="bg-background/50 border border-border rounded-2xl p-8 flex flex-col gap-4">
            <div className="text-text-muted text-[10px] uppercase font-black tracking-[0.2em] mb-2">Entry Intelligence</div>
            <div className="flex justify-between items-center">
              <span className="text-text-dim text-xs font-black uppercase tracking-widest">Entry Benchmark</span>
              <span className="text-white font-black tabular-nums">{formatCurrency(position.entry_price)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-text-dim text-xs font-black uppercase tracking-widest">Quantity</span>
              <span className="text-white font-black tabular-nums">{position.quantity} Contracts</span>
            </div>
            <div className="pt-4 border-t border-border flex justify-between items-center">
              <span className="text-text-dim text-xs font-black uppercase tracking-widest">Cost Basis</span>
              <span className="text-white font-black tabular-nums">{formatCurrency(position.entry_price * position.quantity * 100)}</span>
            </div>
          </div>

          <div className="bg-background/50 border border-border rounded-2xl p-8 flex flex-col gap-4">
            <div className="text-text-muted text-[10px] uppercase font-black tracking-[0.2em] mb-2">Market Dynamics</div>
            <div className="flex justify-between items-center">
              <span className="text-text-dim text-xs font-black uppercase tracking-widest">Current Mark</span>
              <span className="text-white font-black tabular-nums">{formatCurrency(position.current_price || 0)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-text-dim text-xs font-black uppercase tracking-widest">Notional Value</span>
              <span className="text-white font-black tabular-nums">{formatCurrency((position.current_price || 0) * position.quantity * 100)}</span>
            </div>
            <div className="pt-4 border-t border-border flex justify-between items-center">
              <span className="text-text-dim text-xs font-black uppercase tracking-widest">Status Code</span>
              <span className="text-profit font-black uppercase text-[10px] tracking-[0.2em]">ACTIVE_EXPOSURE</span>
            </div>
          </div>
        </div>

        {/* Footer Info */}
        <div className="flex justify-between items-center text-[10px] font-black text-text-dim uppercase tracking-[0.2em] bg-background/50 px-6 py-4 rounded-xl border border-border relative z-10">
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-3">
              <span className="text-white/40">RISK_PROFILE</span>
              <span className="text-white">DERIVATIVE_100X</span>
            </div>
            <div className="w-1 h-1 rounded-full bg-border" />
            <div className="flex items-center gap-3">
              <span className="text-white/40">POSITION_ID</span>
              <span className="text-white font-mono">{position.id.slice(0, 12).toUpperCase()}</span>
            </div>
          </div>
          
          <div className="italic tracking-normal normal-case opacity-40">
            "Paper trading for intellectual dominance."
          </div>
        </div>
      </div>
    </ShareLayout>
  );
};

export default SharePosition;
