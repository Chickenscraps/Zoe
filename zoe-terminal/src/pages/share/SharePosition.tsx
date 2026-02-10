import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ShareLayout } from '../../components/ShareLayout';
import { supabase } from '../../lib/supabaseClient';

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
    <ShareLayout title="Open Position">
      <div className="flex flex-col h-full justify-between">
        {/* Header Section */}
        <div className="flex justify-between items-start">
          <div>
            <div className="text-4xl font-bold text-white tracking-tighter flex items-center gap-3">
              {position.symbol}
              <span className={`text-xs px-2 py-1 rounded border ${
                position.direction === 'long' ? 'bg-green-500/10 border-green-500/50 text-green-400' : 'bg-red-500/10 border-red-500/50 text-red-400'
              }`}>
                {position.direction.toUpperCase()}
              </span>
            </div>
            <div className="text-zinc-500 font-mono mt-1 text-sm">
              STRATEGY: {position.strategy.toUpperCase()}
            </div>
          </div>
          
          <div className="text-right">
            <div className={`text-5xl font-bold tracking-tighter ${isGreen ? 'text-green-400' : 'text-red-400'}`}>
              {isGreen ? '+' : ''}{position.pnl_percent?.toFixed(2)}%
            </div>
            <div className={`text-xl font-mono ${isGreen ? 'text-green-500/70' : 'text-red-500/70'}`}>
              {isGreen ? '+' : ''}${position.pnl_open?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </div>
        </div>

        {/* Body Section - Market Data */}
        <div className="grid grid-cols-2 gap-8 my-8">
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
            <div className="text-zinc-500 text-xs font-mono mb-2 uppercase tracking-widest">Entry Detail</div>
            <div className="flex justify-between items-center mb-1">
              <span className="text-zinc-400 text-sm">Entry Price</span>
              <span className="text-white font-mono">${position.entry_price.toFixed(2)}</span>
            </div>
            <div className="flex justify-between items-center mb-1">
              <span className="text-zinc-400 text-sm">Quantity</span>
              <span className="text-white font-mono">{position.quantity} Contracts</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-zinc-400 text-sm">Cost Basis</span>
              <span className="text-white font-mono">${(position.entry_price * position.quantity * 100).toLocaleString()}</span>
            </div>
          </div>

          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
            <div className="text-zinc-500 text-xs font-mono mb-2 uppercase tracking-widest">Market Comparison</div>
            <div className="flex justify-between items-center mb-1">
              <span className="text-zinc-400 text-sm">Last Mark</span>
              <span className="text-white font-mono">${position.current_price?.toFixed(2)}</span>
            </div>
            <div className="flex justify-between items-center mb-1">
              <span className="text-zinc-400 text-sm">Current Value</span>
              <span className="text-white font-mono">${(position.current_price! * position.quantity * 100).toLocaleString()}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-zinc-400 text-sm">Status</span>
              <span className="text-blue-400 font-mono uppercase text-xs">Active Exposure</span>
            </div>
          </div>
        </div>

        {/* Footer Info */}
        <div className="border-t border-zinc-800 pt-6 flex justify-between items-center">
          <div className="flex items-center gap-6">
            <div>
              <div className="text-zinc-600 text-[10px] uppercase font-mono tracking-widest mb-1">Risk Profile</div>
              <div className="text-zinc-400 text-xs font-mono">Standard Options (100x)</div>
            </div>
            <div className="h-8 w-px bg-zinc-800"></div>
            <div>
              <div className="text-zinc-600 text-[10px] uppercase font-mono tracking-widest mb-1">Position ID</div>
              <div className="text-zinc-400 text-xs font-mono">{position.id.slice(0, 12)}...</div>
            </div>
          </div>
          
          <div className="text-zinc-700 font-mono text-[10px] italic">
            "Paper trading for intellectual dominance."
          </div>
        </div>
      </div>
    </ShareLayout>
  );
};

export default SharePosition;
