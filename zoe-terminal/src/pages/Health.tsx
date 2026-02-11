import { useEffect, useState } from 'react';
import { Activity, Server, Database as DbIcon, Shield, Wifi } from 'lucide-react';
import { StatusChip } from '../components/StatusChip';
import { formatDate } from '../lib/utils';
import { supabase } from '../lib/supabaseClient';
import type { Database } from '../lib/types';

type HealthHeartbeat = Database['public']['Tables']['health_heartbeat']['Row'];

const ICON_MAP: Record<string, any> = {
  'data_provider': Wifi,
  'trading_engine': Server,
  'supabase': DbIcon,
  'risk_manager': Shield,
  'discord': Activity,
};

function getIcon(component: string) {
  const key = Object.keys(ICON_MAP).find(k => component.toLowerCase().includes(k));
  return key ? ICON_MAP[key] : Activity;
}

export default function Health() {
  const [heartbeats, setHeartbeats] = useState<HealthHeartbeat[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchHealth() {
      try {
        const { data, error } = await supabase
          .from('health_heartbeat')
          .select('*')
          .order('last_heartbeat', { ascending: false });

        if (error) throw error;
        if (data) setHeartbeats(data);
      } catch (err) {
        console.error('Error fetching health:', err);
      } finally {
        setLoading(false);
      }
    }
    fetchHealth();

    const subscription = supabase
      .channel('health_updates')
      .on('postgres_changes', {
        event: '*',
        schema: 'public',
        table: 'health_heartbeat'
      }, () => { fetchHealth(); })
      .subscribe();

    return () => { subscription.unsubscribe(); };
  }, []);

  const allOk = heartbeats.length > 0 && heartbeats.every(h => h.status === 'ok');

  if (loading) {
    return <div className="text-text-secondary animate-pulse p-8">Loading health status...</div>;
  }

  return (
    <div className="space-y-6">
       <div className="flex justify-between items-center">
          <h2 className="text-xl font-semibold text-white">System Health</h2>
          <div className="flex items-center gap-2">
             <div className={`w-2 h-2 rounded-full animate-pulse ${allOk ? 'bg-emerald-500' : 'bg-warning'}`} />
             <span className={`text-sm font-medium ${allOk ? 'text-emerald-500' : 'text-warning'}`}>
               {allOk ? 'Operational' : 'Degraded'}
             </span>
          </div>
       </div>

       {heartbeats.length > 0 ? (
       <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
           {heartbeats.map((hb) => {
               const Icon = getIcon(hb.component);
               const meta = (hb.details as any) ?? {};
               return (
                   <div key={hb.id} className="bg-surface border border-border rounded-lg p-5">
                       <div className="flex justify-between items-start mb-4">
                           <div className="flex items-center gap-3">
                               <div className="p-2 bg-surface-highlight rounded-lg text-text-secondary">
                                   <Icon className="w-5 h-5" />
                               </div>
                               <div>
                                   <h3 className="font-semibold text-white text-sm">{hb.component}</h3>
                                   <p className="text-xs text-text-muted">Last: {formatDate(hb.last_heartbeat)}</p>
                               </div>
                           </div>
                           <StatusChip status={hb.status as any} label={hb.status.toUpperCase()} />
                       </div>

                       {(meta.latency || meta.uptime) && (
                       <div className="grid grid-cols-2 gap-4 text-sm mt-4 pt-4 border-t border-border">
                           {meta.latency && (
                           <div>
                               <p className="text-text-secondary text-xs mb-1">Latency</p>
                               <p className="font-mono text-white">{meta.latency}</p>
                           </div>
                           )}
                           {meta.uptime && (
                           <div>
                               <p className="text-text-secondary text-xs mb-1">Uptime</p>
                               <p className="font-mono text-white">{meta.uptime}</p>
                           </div>
                           )}
                       </div>
                       )}

                       {meta.message && (
                           <div className="mt-3 text-xs bg-yellow-500/10 text-yellow-500 px-2 py-1.5 rounded border border-yellow-500/20">
                               {meta.message}
                           </div>
                       )}
                   </div>
               );
           })}
       </div>
       ) : (
         <div className="card-premium p-12 text-center text-text-muted">No health data available.</div>
       )}
    </div>
  );
}
