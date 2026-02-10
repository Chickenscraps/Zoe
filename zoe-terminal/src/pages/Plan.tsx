import { useState } from 'react';
import type { Database } from '../lib/types';
import { DataTable } from '../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import { cn } from '../lib/utils';
import { Lock, FileEdit, CheckCircle } from 'lucide-react';

type PlanItem = Database['public']['Tables']['daily_gameplan_items']['Row'];

export default function Plan() {
  const [activeTab, setActiveTab] = useState<'draft' | 'refined' | 'locked'>('locked');

  // Mock data
  const planItems: PlanItem[] = [
      {
          id: 'p1', plan_id: 'dp1', symbol: 'SPY', 
          catalyst_summary: 'CPI Print', regime: 'High Vol', 
          ivr_tech_snapshot: 'IVR 60, res at 440', preferred_strategy: 'Iron Condor',
          risk_tier: 'Tier 1', do_not_trade: false, visual_notes: 'Watch 440 level'
      },
      {
          id: 'p2', plan_id: 'dp1', symbol: 'MSFT', 
          catalyst_summary: 'None', regime: 'Range', 
          ivr_tech_snapshot: 'IVR 20', preferred_strategy: 'Credit Spread',
          risk_tier: 'Tier 2', do_not_trade: false, visual_notes: null
      }
  ];

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
             onClick={() => setActiveTab('draft')}
             className={cn(
                 "px-6 py-3 text-sm font-medium flex items-center gap-2 border-b-2 transition-colors",
                 activeTab === 'draft' ? "border-brand text-white" : "border-transparent text-text-secondary hover:text-white"
             )}
           >
               <FileEdit className="w-4 h-4" /> Draft (T-15)
           </button>
           <button 
             onClick={() => setActiveTab('refined')}
             className={cn(
                 "px-6 py-3 text-sm font-medium flex items-center gap-2 border-b-2 transition-colors",
                 activeTab === 'refined' ? "border-brand text-white" : "border-transparent text-text-secondary hover:text-white"
             )}
           >
               <CheckCircle className="w-4 h-4" /> Refined (T-10)
           </button>
           <button 
             onClick={() => setActiveTab('locked')}
             className={cn(
                 "px-6 py-3 text-sm font-medium flex items-center gap-2 border-b-2 transition-colors",
                 activeTab === 'locked' ? "border-brand text-white" : "border-transparent text-text-secondary hover:text-white"
             )}
           >
               <Lock className="w-4 h-4" /> Locked (T-5)
           </button>
       </div>

       <div className="min-h-[400px]">
           {activeTab === 'locked' ? (
               <DataTable columns={columns} data={planItems} />
           ) : (
               <div className="flex items-center justify-center h-40 text-text-muted border border-dashed border-border rounded-lg">
                   {activeTab === 'draft' ? 'Drafting in progress...' : 'Refining plan...'}
               </div>
           )}
       </div>
    </div>
  );
}
