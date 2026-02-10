import { useState, useEffect } from 'react';
import type { Database } from '../lib/types';
import { DataTable } from '../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import { cn } from '../lib/utils';
import { Lock, FileEdit, CheckCircle } from 'lucide-react';
import { supabase } from '../lib/supabaseClient';

type PlanItem = Database['public']['Tables']['daily_gameplan_items']['Row'];

export default function Plan() {
  const [activeTab, setActiveTab] = useState<'draft' | 'refined' | 'locked'>('locked');
  const [planItems, setPlanItems] = useState<PlanItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPlan = async () => {
        try {
            setLoading(true);
            const today = new Date().toISOString().split('T')[0];
            
            // 1. Get the gameplan record for today
            const { data: plan, error: planError } = await supabase
                .from('daily_gameplans')
                .select('id, status')
                .eq('date', today)
                .single();

            if (planError && planError.code !== 'PGRST116') { // Ignore "no rows returned"
                throw planError;
            }

            if (plan) {
                const planData = plan as any;
                setActiveTab(planData.status);
                
                // 2. Get items for this plan
                const { data: items, error: itemsError } = await supabase
                    .from('daily_gameplan_items')
                    .select('*')
                    .eq('plan_id', planData.id);
                
                if (itemsError) throw itemsError;
                if (items) setPlanItems(items);
            } else {
                setPlanItems([]);
            }
        } catch (err) {
            console.error('Error fetching plan:', err);
        } finally {
            setLoading(false);
        }
    };

    fetchPlan();
  }, []);

  const columns: ColumnDef<PlanItem>[] = [
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

  return (
    <div className="space-y-10">
       <div className="flex justify-between items-end border-b border-border pb-8">
          <div>
            <h2 className="text-3xl font-black text-white tracking-tighter">Autonomous Gameplan</h2>
            <p className="text-sm text-text-muted mt-2 font-medium tracking-tight">System-generated strategy for the current session.</p>
          </div>
          <div className="text-[10px] font-black text-text-muted uppercase tracking-[0.2em]">
             Snapshot as of {new Date().toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
          </div>
       </div>

       {/* Tabs */}
       <div className="flex gap-8 border-b border-border/50">
           {[
             { id: 'draft', label: 'Draft', icon: FileEdit },
             { id: 'refined', label: 'Refined', icon: CheckCircle },
             { id: 'locked', label: 'Locked', icon: Lock }
           ].map((tab) => (
             <button 
               key={tab.id}
               className={cn(
                   "pb-4 text-[10px] font-black uppercase tracking-[0.2em] flex items-center gap-2 border-b-2 transition-all duration-300",
                   activeTab === tab.id ? "border-profit text-white" : "border-transparent text-text-muted hover:text-text-secondary"
               )}
             >
                 <tab.icon className={cn("w-3.5 h-3.5", activeTab === tab.id ? "text-profit" : "")} /> {tab.label}
             </button>
           ))}
       </div>

       <div className="min-h-[400px]">
           {loading ? (
                <div className="flex flex-col items-center justify-center h-64 text-text-muted animate-pulse gap-4">
                    <div className="w-12 h-12 border-2 border-border border-t-profit rounded-full animate-spin" />
                    <span className="text-[10px] font-black uppercase tracking-widest italic">Interpreting market signals...</span>
                </div>
           ) : planItems.length > 0 ? (
                <DataTable columns={columns} data={planItems} />
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
