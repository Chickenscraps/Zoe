import React, { useEffect, useState } from 'react';
import { ShareLayout } from '../../components/ShareLayout';
import { supabase } from '../../lib/supabaseClient';

interface GamePlan {
  id: string;
  date: string;
  status: string;
}

interface GamePlanItem {
  id: string;
  symbol: string;
  regime: string;
  preferred_strategy: string;
  catalyst_summary: string;
  risk_tier: string;
}

const SharePlan: React.FC = () => {
  const [plan, setPlan] = useState<GamePlan | null>(null);
  const [items, setItems] = useState<GamePlanItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPlan = async () => {
      const today = new Date().toISOString().split('T')[0];
      
      const { data: planData } = await supabase
        .from('daily_gameplans')
        .select('*')
        .eq('date', today)
        .single();

      if (planData) {
        setPlan(planData);
        
        const { data: itemData } = await supabase
          .from('daily_gameplan_items')
          .select('*')
          .eq('plan_id', (planData as any).id);
        
        if (itemData) setItems(itemData as any[]);
      }
      setLoading(false);
    };

    fetchPlan();
  }, []);

  if (loading) return <div className="p-8 text-white">Loading gameplan...</div>;
  if (!plan) return <div className="p-8 text-white">No gameplan found for today</div>;

  return (
    <ShareLayout title="Daily Gameplan">
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="flex justify-between items-end mb-8 border-b border-zinc-800 pb-6">
          <div>
             <div className="text-zinc-500 font-mono text-xs uppercase tracking-[0.2em] mb-1">Market Logic</div>
             <h1 className="text-4xl font-bold text-white tracking-tighter">PRE-MARKET PROTOCOL</h1>
          </div>
          <div className="text-right">
             <div className="text-zinc-500 font-mono text-xs uppercase tracking-[0.2em] mb-1">Execution Date</div>
             <div className="text-xl text-white font-bold">{new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</div>
          </div>
        </div>

        {/* Plan Table */}
        <div className="flex-1 overflow-hidden">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-zinc-800/50">
                <th className="py-3 font-mono text-[10px] text-zinc-600 uppercase tracking-widest">Symbol</th>
                <th className="py-3 font-mono text-[10px] text-zinc-600 uppercase tracking-widest">Strategy</th>
                <th className="py-3 font-mono text-[10px] text-zinc-600 uppercase tracking-widest">Regime</th>
                <th className="py-3 font-mono text-[10px] text-zinc-600 uppercase tracking-widest text-right">Risk</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/30">
              {items.slice(0, 5).map((item) => (
                <tr key={item.id}>
                  <td className="py-4">
                    <span className="text-lg font-bold text-white">{item.symbol}</span>
                    <div className="text-[10px] text-zinc-500 font-mono italic max-w-xs truncate">{item.catalyst_summary}</div>
                  </td>
                  <td className="py-4 font-mono text-sm text-zinc-300">{item.preferred_strategy}</td>
                  <td className="py-4">
                    <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                      {item.regime}
                    </span>
                  </td>
                  <td className="py-4 text-right">
                    <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                      item.risk_tier === 'Tier 1' ? 'bg-green-500/10 text-green-500 border border-green-500/30' : 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/30'
                    }`}>
                      {item.risk_tier.toUpperCase()}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          
          {items.length > 5 && (
            <div className="mt-4 text-center text-zinc-600 font-mono text-[10px] uppercase tracking-widest">
              + {items.length - 5} more tickers in full report
            </div>
          )}
        </div>

        {/* Brand Footer */}
        <div className="mt-8 pt-6 border-t border-zinc-800 flex justify-between items-center text-[10px] font-mono tracking-widest text-zinc-600">
          <div>ZOE V4 | AUTONOMOUS RESEARCH LAYER</div>
          <div className="bg-white text-black px-2 py-0.5 font-bold">LOCKED</div>
        </div>
      </div>
    </ShareLayout>
  );
};

export default SharePlan;
