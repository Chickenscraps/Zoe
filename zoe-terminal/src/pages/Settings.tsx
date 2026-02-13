import { useState, useEffect } from 'react';
import type { Database } from '../lib/types';
import { Download, Shield, Trash2, AlertTriangle, Lock } from 'lucide-react';
import { supabase } from '../lib/supabaseClient';

import { useDashboardData } from '../hooks/useDashboardData';
import { useAuth } from '../lib/AuthContext';
import { formatCurrency } from '../lib/utils';

type Config = Database['public']['Tables']['config']['Row'];

export default function Settings() {
  const { isGuest } = useAuth();
  const [config, setConfig] = useState<Config[]>([]);
  const [loading, setLoading] = useState(true);
  const [killConfirm, setKillConfirm] = useState(false);
  const [cacheCleared, setCacheCleared] = useState(false);
  const [pnlResetConfirm, setPnlResetConfirm] = useState(false);
  const [pnlResetting, setPnlResetting] = useState(false);

  const { cryptoCash, dailyNotional, healthSummary, holdingsRows, cryptoOrders } = useDashboardData();

  useEffect(() => {
      async function fetchConfig() {
        try {
          const { data, error } = await supabase
            .from('config')
            .select('*')
            .order('key');
          if (error) throw error;
          if (data) setConfig(data);
        } catch (err) {
          console.error('Error fetching config:', err);
        } finally {
          setLoading(false);
        }
      }
      fetchConfig();
  }, []);

  const handleExport = () => {
    const exportData = {
      exported_at: new Date().toISOString(),
      cash: cryptoCash,
      holdings: holdingsRows,
      orders: cryptoOrders,
      config,
    };
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `zoe-export-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleClearCache = () => {
    localStorage.clear();
    sessionStorage.clear();
    setCacheCleared(true);
    setTimeout(() => setCacheCleared(false), 3000);
  };

  return (
    <div className="space-y-8 max-w-4xl">
       <div className="flex justify-between items-center">
          <div>
            <h2 className="font-pixel text-[0.55rem] uppercase tracking-[0.08em] text-earth-700">Settings</h2>
            <p className="text-sm text-text-secondary">
              System configuration (read only)
            </p>
          </div>
          <div className="flex gap-2">
              <button
                onClick={handleExport}
                className="flex items-center gap-2 px-3 py-2 bg-cream-100 text-earth-700 border-2 border-earth-700/10 rounded-[4px] hover:bg-paper-100 transition-colors text-sm"
              >
                  <Download className="w-4 h-4" /> Export Data
              </button>
          </div>
       </div>

       {/* Runtime Status */}
       <div className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] overflow-hidden">
           <div className="px-6 py-4 border-b border-earth-700/10 bg-cream-100/40">
               <h3 className="font-medium text-sm flex items-center gap-2">
                 <Shield className="w-4 h-4 text-text-muted" /> Runtime Status
               </h3>
           </div>
           <div className="divide-y divide-earth-700/10">
               <div className="grid grid-cols-1 md:grid-cols-3 px-6 py-4">
                   <div className="font-mono text-sm text-text-secondary">System Status</div>
                   <div className="md:col-span-2 font-mono text-sm">
                     <span className={healthSummary.status === 'LIVE' ? "text-profit font-bold" : "text-warning font-bold"}>
                       {healthSummary.status}
                     </span>
                     <span className="text-text-muted ml-2 text-xs">{healthSummary.reason}</span>
                   </div>
               </div>
               <div className="grid grid-cols-1 md:grid-cols-3 px-6 py-4">
                   <div className="font-mono text-sm text-text-secondary">Cash Available</div>
                   <div className="md:col-span-2 font-mono text-sm text-earth-700">{formatCurrency(cryptoCash?.cash_available ?? 0)}</div>
               </div>
               <div className="grid grid-cols-1 md:grid-cols-3 px-6 py-4">
                   <div className="font-mono text-sm text-text-secondary">Buying Power</div>
                   <div className="md:col-span-2 font-mono text-sm text-earth-700">{formatCurrency(cryptoCash?.buying_power ?? 0)}</div>
               </div>
               <div className="grid grid-cols-1 md:grid-cols-3 px-6 py-4">
                   <div className="font-mono text-sm text-text-secondary">Daily Notional Used</div>
                   <div className="md:col-span-2 font-mono text-sm text-earth-700">
                     {formatCurrency(dailyNotional?.notional_used ?? 0)} / {formatCurrency(dailyNotional?.notional_limit ?? 50)}
                   </div>
               </div>
               <div className="grid grid-cols-1 md:grid-cols-3 px-6 py-4">
                   <div className="font-mono text-sm text-text-secondary">Open Positions</div>
                   <div className="md:col-span-2 font-mono text-sm text-earth-700">{holdingsRows.length}</div>
               </div>
               <div className="grid grid-cols-1 md:grid-cols-3 px-6 py-4">
                   <div className="font-mono text-sm text-text-secondary">Last Reconcile</div>
                   <div className="md:col-span-2 font-mono text-sm text-earth-700">
                     {healthSummary.lastReconcile
                       ? new Date(healthSummary.lastReconcile).toLocaleString()
                       : 'Never'}
                   </div>
               </div>
           </div>
       </div>

       {/* Config Table */}
       <div className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] overflow-hidden">
           <div className="px-6 py-4 border-b border-earth-700/10 bg-cream-100/40">
               <h3 className="font-medium text-sm">System Configuration</h3>
           </div>

           {loading ? (
             <div className="p-6 text-text-muted animate-pulse">Loading configuration...</div>
           ) : config.length > 0 ? (
           <div className="divide-y divide-earth-700/10">
               {config.map(item => (
                   <div key={item.key} className="grid grid-cols-1 md:grid-cols-3 px-6 py-4 hover:bg-sakura-500/5 transition-colors">
                       <div className="font-mono text-sm text-text-secondary">{item.key}</div>
                       <div className="md:col-span-2 font-mono text-sm text-earth-700 break-words">
                           {typeof item.value === 'object' ? JSON.stringify(item.value) : String(item.value)}
                       </div>
                   </div>
               ))}
           </div>
           ) : (
             <div className="p-6 text-text-muted text-sm">No stored configuration keys. Runtime settings are shown above.</div>
           )}
       </div>

       {/* Admin Actions */}
       <div className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] p-6">
           <h3 className="font-medium text-sm mb-4 text-text-secondary flex items-center gap-2">
             Admin Actions
             {isGuest && <span className="inline-flex items-center gap-1 text-[10px] text-amber-500/70 font-bold"><Lock className="w-3 h-3" /> View Only</span>}
           </h3>
           {isGuest ? (
             <div className="text-sm text-text-muted italic">Admin actions are disabled for guest access.</div>
           ) : (
           <div className="flex gap-4 flex-wrap">
               {!killConfirm ? (
                 <button
                   onClick={() => setKillConfirm(true)}
                   className="flex items-center gap-2 px-4 py-2 bg-red-500/10 text-red-600 border-2 border-red-500/20 rounded-[4px] hover:bg-red-500/15 transition-colors text-sm font-medium"
                 >
                   <AlertTriangle className="w-4 h-4" /> Emergency Pause
                 </button>
               ) : (
                 <div className="flex items-center gap-2">
                   <span className="text-xs text-red-400 font-bold">This pauses all automation. Confirm?</span>
                   <button
                     onClick={async () => {
                       try {
                         await supabase.from('config').upsert({
                           key: 'kill_switch',
                           value: true,
                           instance_id: 'primary-v4-live',
                         });
                         setKillConfirm(false);
                         alert('Emergency pause activated. Automation paused.');
                       } catch {
                         alert('Failed to activate emergency pause.');
                       }
                     }}
                     className="px-3 py-1.5 bg-red-500 text-cream-100 rounded-[4px] text-sm font-bold"
                   >
                     CONFIRM KILL
                   </button>
                   <button
                     onClick={() => setKillConfirm(false)}
                     className="px-3 py-1.5 bg-cream-100 text-text-muted rounded-[4px] border border-earth-700/10 text-sm"
                   >
                     Cancel
                   </button>
                 </div>
               )}
               <button
                 onClick={handleClearCache}
                 className="flex items-center gap-2 px-4 py-2 bg-cream-100 text-earth-700 rounded-[4px] border-2 border-earth-700/10 hover:bg-paper-100 transition-colors text-sm font-medium"
               >
                   <Trash2 className="w-4 h-4" />
                   {cacheCleared ? 'Cache Cleared!' : 'Clear Cache'}
               </button>
               {!pnlResetConfirm ? (
                 <button
                   onClick={() => setPnlResetConfirm(true)}
                   className="flex items-center gap-2 px-4 py-2 bg-orange-500/10 text-orange-600 border-2 border-orange-500/20 rounded-[4px] hover:bg-orange-500/15 transition-colors text-sm font-medium"
                 >
                   <Trash2 className="w-4 h-4" /> Reset P&L Data
                 </button>
               ) : (
                 <div className="flex items-center gap-2">
                   <span className="text-xs text-orange-400 font-bold">This clears all P&L history. Confirm?</span>
                   <button
                     onClick={async () => {
                       setPnlResetting(true);
                       try {
                         await supabase.from('crypto_cash_snapshots').delete().neq('id', '0');
                         await supabase.from('pnl_daily').delete().neq('date', '');
                         setPnlResetConfirm(false);
                         window.location.reload();
                       } catch {
                         alert('Failed to reset P&L data.');
                       } finally {
                         setPnlResetting(false);
                       }
                     }}
                     disabled={pnlResetting}
                     className="px-3 py-1.5 bg-orange-500 text-cream-100 rounded-[4px] text-sm font-bold disabled:opacity-50"
                   >
                     {pnlResetting ? 'Resetting...' : 'CONFIRM RESET'}
                   </button>
                   <button
                     onClick={() => setPnlResetConfirm(false)}
                     className="px-3 py-1.5 bg-cream-100 text-text-muted rounded-[4px] border border-earth-700/10 text-sm"
                   >
                     Cancel
                   </button>
                 </div>
               )}
           </div>
           )}
       </div>
    </div>
  );
}
