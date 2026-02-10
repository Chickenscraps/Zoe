import { Activity, Server, Database as DbIcon, Shield, Wifi } from 'lucide-react';
import { StatusChip } from '../components/StatusChip';
import { formatDate } from '../lib/utils';

export default function Health() {
  const services = [
      { name: 'Data Provider (Polygon)', status: 'ok', latency: '45ms', uptime: '99.9%', icon: Wifi },
      { name: 'Trading Engine', status: 'ok', latency: '12ms', uptime: '100%', icon: Server },
      { name: 'Supabase Database', status: 'ok', latency: '85ms', uptime: '99.99%', icon: DbIcon },
      { name: 'Risk Manager', status: 'warning', latency: '-', uptime: '98%', message: 'High load detected', icon: Shield },
      { name: 'Discord Gateway', status: 'ok', latency: '120ms', uptime: '99.5%', icon: Activity },
  ];

  return (
    <div className="space-y-6">
       <div className="flex justify-between items-center">
          <h2 className="text-xl font-bold text-white">System Health</h2>
          <div className="flex items-center gap-2">
             <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
             <span className="text-sm text-emerald-500 font-medium">Operational</span>
          </div>
       </div>

       <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
           {services.map((service, i) => {
               const Icon = service.icon;
               return (
                   <div key={i} className="bg-surface border border-border rounded-lg p-5">
                       <div className="flex justify-between items-start mb-4">
                           <div className="flex items-center gap-3">
                               <div className="p-2 bg-surface-highlight rounded-lg text-text-secondary">
                                   <Icon className="w-5 h-5" />
                               </div>
                               <div>
                                   <h3 className="font-bold text-white text-sm">{service.name}</h3>
                                   <p className="text-xs text-text-muted">Service ID: svc-{i}</p>
                               </div>
                           </div>
                           <StatusChip status={service.status as any} label={service.status.toUpperCase()} />
                       </div>
                       
                       <div className="grid grid-cols-2 gap-4 text-sm mt-4 pt-4 border-t border-border">
                           <div>
                               <p className="text-text-secondary text-xs mb-1">Latency</p>
                               <p className="font-mono text-white">{service.latency}</p>
                           </div>
                           <div>
                               <p className="text-text-secondary text-xs mb-1">Uptime (24h)</p>
                               <p className="font-mono text-white">{service.uptime}</p>
                           </div>
                       </div>
                       
                       {service.message && (
                           <div className="mt-3 text-xs bg-yellow-500/10 text-yellow-500 px-2 py-1.5 rounded border border-yellow-500/20">
                               {service.message}
                           </div>
                       )}
                   </div>
               );
           })}
       </div>

       <div className="bg-surface border border-border rounded-lg p-6">
           <h3 className="font-medium text-sm mb-4 text-text-secondary">Recent Heartbeats</h3>
           <div className="space-y-2">
               {[1,2,3,4,5].map(i => (
                   <div key={i} className="flex justify-between items-center text-sm py-2 border-b border-border/50 last:border-0">
                       <div className="flex items-center gap-3">
                           <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                           <span className="font-mono text-text-muted">{formatDate(new Date(Date.now() - i * 5000 * 60).toISOString())}</span>
                       </div>
                       <span className="text-text-primary">System healthy, all checks passed.</span>
                       <span className="font-mono text-xs text-text-secondary">Load: {12 + i}%</span>
                   </div>
               ))}
           </div>
       </div>
    </div>
  );
}
