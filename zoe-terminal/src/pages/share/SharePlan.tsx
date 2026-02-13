import React, { useEffect, useState } from 'react';
import { ShareLayout } from '../../components/ShareLayout';
import { supabase } from '../../lib/supabaseClient';
import { Lock } from 'lucide-react';
import { cn } from '../../lib/utils';

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

  if (loading) return <div className="p-8 text-earth-700">Loading gameplan...</div>;
  if (!plan) return <div className="p-8 text-earth-700">No gameplan found for today</div>;

  return (
    <ShareLayout title="STRATEGIC_PRE_MARKET_PROTOCOL">
      <div 
        data-testid="plan-ticket" 
        className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] p-12 w-[1100px] flex flex-col gap-10 relative overflow-hidden"
      >
        {/* Header */}
        <div className="flex justify-between items-end pb-8 border-b border-earth-700/10 relative z-10">
          <div>
             <div className="text-sakura-700 font-semibold text-[10px] uppercase tracking-[0.3em] mb-3">Market Logic Layer</div>
             <h1 className="text-5xl font-semibold text-earth-700 tracking-tighter uppercase">Protocol Status: <span className="text-sakura-700">Active</span></h1>
          </div>
          <div className="text-right">
             <div className="text-text-muted font-semibold text-[10px] uppercase tracking-[0.3em] mb-3">Release Timestamp</div>
             <div className="text-2xl text-earth-700 font-semibold tracking-tight tabular-nums">{new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).toUpperCase()}</div>
          </div>
        </div>

        {/* Plan Table */}
        <div className="flex-1 overflow-hidden relative z-10">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-earth-700/10">
                <th className="py-4 px-4 font-semibold text-[10px] text-text-muted uppercase tracking-[0.2em]">Asset Symbol</th>
                <th className="py-4 px-4 font-semibold text-[10px] text-text-muted uppercase tracking-[0.2em]">Execution Strategy</th>
                <th className="py-4 px-4 font-semibold text-[10px] text-text-muted uppercase tracking-[0.2em]">Market Regime</th>
                <th className="py-4 px-4 font-semibold text-[10px] text-text-muted uppercase tracking-[0.2em] text-right">Risk Tier</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-earth-700/10">
              {items.slice(0, 6).map((item) => (
                <tr key={item.id} className="group hover:bg-sakura-500/5 transition-colors">
                  <td className="py-6 px-4">
                    <span className="text-2xl font-semibold text-earth-700 tracking-tighter tabular-nums">{item.symbol}</span>
                    <div className="text-[11px] text-text-muted font-medium italic mt-1 max-w-xs truncate opacity-70 group-hover:opacity-100 transition-opacity">{item.catalyst_summary}</div>
                  </td>
                  <td className="py-6 px-4 font-semibold text-xs text-earth-700 uppercase tracking-tight">{item.preferred_strategy}</td>
                  <td className="py-6 px-4">
                    <span className="text-[10px] px-3 py-1 rounded-[4px] bg-earth-700/5 text-earth-700 border border-earth-700/10 font-semibold uppercase tracking-widest">
                      {item.regime}
                    </span>
                  </td>
                  <td className="py-6 px-4 text-right">
                    <span className={cn(
                      "text-[10px] px-3 py-1 rounded-[4px] font-semibold uppercase tracking-[0.15em]",
                      item.risk_tier === 'Tier 1' ? 'bg-profit/10 text-profit border border-profit/20' : 'bg-warning/10 text-warning border border-warning/20'
                    )}>
                      {item.risk_tier.toUpperCase()}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          
          {items.length > 6 && (
            <div className="mt-8 text-center text-text-dim font-semibold text-[10px] uppercase tracking-[0.4em] italic opacity-50">
              + {items.length - 6} Additional Nodes Encapsulated in Full Report
            </div>
          )}
        </div>

        {/* Brand Footer */}
        <div className="flex justify-between items-center text-[10px] font-semibold tracking-[0.3em] text-text-dim uppercase mt-4 relative z-10">
          <div className="flex items-center gap-4">
            <span className="text-earth-700/40">System Core</span>
            <div className="w-1 h-1 rounded-full bg-sakura-500/40" />
            <span className="text-earth-700">Autonomous Research Layer</span>
          </div>
          <div className="bg-earth-700 text-cream-100 px-4 py-1.5 font-semibold flex items-center gap-3">
            <Lock className="w-3 h-3" /> SESSION_LOCKED
          </div>
        </div>
      </div>
    </ShareLayout>
  );
};

export default SharePlan;
