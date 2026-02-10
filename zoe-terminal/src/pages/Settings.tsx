import { useState, useEffect } from 'react';
import type { Database } from '../lib/types';
import { Download } from 'lucide-react';

type Config = Database['public']['Tables']['config']['Row'];

export default function Settings() {
  const [config, setConfig] = useState<Config[]>([]);

  useEffect(() => {
      // Mock config
      setConfig([
          { key: 'risk_limit_per_trade_pct', instance_id: 'primary', value: 2.0 },
          { key: 'max_open_positions', instance_id: 'primary', value: 5 },
          { key: 'kill_switch_enabled', instance_id: 'primary', value: false },
          { key: 'scan_interval_minutes', instance_id: 'primary', value: 15 },
          { key: 'data_provider', instance_id: 'primary', value: 'polygon' },
          { key: 'slippage_model', instance_id: 'primary', value: { type: 'fixed', amount: 0.01 } },
      ]);
  }, []);

  return (
    <div className="space-y-8 max-w-4xl">
       <div className="flex justify-between items-center">
          <div>
            <h2 className="text-xl font-bold text-white">Settings</h2>
            <p className="text-sm text-text-secondary">Configuration for instance: <span className="text-white font-mono">primary-v4-live</span></p>
          </div>
          <div className="flex gap-2">
              <button className="flex items-center gap-2 px-3 py-2 bg-surface text-text-primary border border-border rounded hover:bg-surface-highlight transition-colors text-sm">
                  <Download className="w-4 h-4" /> Export Data
              </button>
          </div>
       </div>

       <div className="bg-surface border border-border rounded-lg overflow-hidden">
           <div className="px-6 py-4 border-b border-border bg-surface-highlight/20">
               <h3 className="font-medium text-sm">System Configuration (Read Only)</h3>
           </div>
           
           <div className="divide-y divide-border">
               {config.map(item => (
                   <div key={item.key} className="grid grid-cols-1 md:grid-cols-3 px-6 py-4 hover:bg-surface-highlight/30 transition-colors">
                       <div className="font-mono text-sm text-text-secondary">{item.key}</div>
                       <div className="md:col-span-2 font-mono text-sm text-white break-words">
                           {typeof item.value === 'object' ? JSON.stringify(item.value) : String(item.value)}
                       </div>
                   </div>
               ))}
           </div>
       </div>

       <div className="bg-surface border border-border rounded-lg p-6">
           <h3 className="font-medium text-sm mb-4 text-text-secondary">Admin Actions</h3>
           <div className="flex gap-4">
               <button className="px-4 py-2 bg-red-500/10 text-red-500 border border-red-500/20 rounded hover:bg-red-500/20 transition-colors text-sm font-medium">
                   Emergency Kill Switch
               </button>
               <button className="px-4 py-2 bg-surface-highlight text-text-primary rounded hover:bg-border transition-colors text-sm font-medium">
                   Clear Cache
               </button>
           </div>
       </div>
    </div>
  );
}
