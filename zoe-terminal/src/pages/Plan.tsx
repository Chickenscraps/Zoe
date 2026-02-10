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
      { header: 'Symbol', accessorKey: 'symbol', cell: i => <span className="font-bold text-white">{i.getValue() as string}</span> },
      { header: 'Regime', accessorKey: 'regime' },
      { header: 'Strategy', accessorKey: 'preferred_strategy' },
      { header: 'Catalyst', accessorKey: 'catalyst_summary' },
      { 
          header: 'Risk', 
          accessorKey: 'risk_tier',
          cell: i => <span className={cn(
              "text-xs px-2 py-0.5 rounded border",
              i.getValue() === 'Tier 1' ? "bg-profit/10 text-profit border-profit/20" : "bg-warning/10 text-warning border-warning/20"
          )}>{i.getValue() as string}</span>
      },
      { header: 'Notes', accessorKey: 'ivr_tech_snapshot', cell: i => <span className="text-xs text-text-muted">{i.getValue() as string}</span> }
  ];

  return (
    <div className="space-y-6">
       <div className="flex justify-between items-center">
          <h2 className="text-xl font-bold text-white">Pre-Market Plan</h2>
          <div className="text-sm text-text-secondary">
             for {new Date().toLocaleDateString()}
          </div>
       </div>

       {/* Tabs */}
       <div className="flex border-b border-border">
           <button 
             className={cn(
                 "px-6 py-3 text-sm font-medium flex items-center gap-2 border-b-2 transition-colors",
                 activeTab === 'draft' ? "border-brand text-white" : "border-transparent text-text-secondary"
             )}
           >
               <FileEdit className="w-4 h-4" /> Draft
           </button>
           <button 
             className={cn(
                 "px-6 py-3 text-sm font-medium flex items-center gap-2 border-b-2 transition-colors",
                 activeTab === 'refined' ? "border-brand text-white" : "border-transparent text-text-secondary"
             )}
           >
               <CheckCircle className="w-4 h-4" /> Refined
           </button>
           <button 
             className={cn(
                 "px-6 py-3 text-sm font-medium flex items-center gap-2 border-b-2 transition-colors",
                 activeTab === 'locked' ? "border-brand text-white" : "border-transparent text-text-secondary"
             )}
           >
               <Lock className="w-4 h-4" /> Locked
           </button>
       </div>

       <div className="min-h-[400px]">
           {loading ? (
                <div className="flex items-center justify-center h-40 text-text-muted animate-pulse">
                    Loading today's gameplan...
                </div>
           ) : planItems.length > 0 ? (
                <DataTable columns={columns} data={planItems} />
           ) : (
                <div className="flex flex-col items-center justify-center h-40 text-text-muted border border-dashed border-border rounded-lg space-y-2">
                    <p>No gameplan found for today.</p>
                    <p className="text-xs italic text-text-secondary">Zoe hasn't generated the market analysis yet.</p>
                </div>
           )}
       </div>
    </div>
  );
}
