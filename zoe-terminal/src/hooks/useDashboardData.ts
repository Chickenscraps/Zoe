import { useEffect, useState } from 'react';
import { supabase } from '../lib/supabaseClient';
import type { Database } from '../lib/types';

type PnlDaily = Database['public']['Tables']['pnl_daily']['Row'];
type AuditLog = Database['public']['Tables']['audit_log']['Row'];
type HealthHeartbeat = Database['public']['Tables']['health_heartbeat']['Row'];

export function useDashboardData(instanceId: string = 'primary-v4-live') {
  const [pnlHistory, setPnlHistory] = useState<PnlDaily[]>([]);
  const [recentEvents, setRecentEvents] = useState<AuditLog[]>([]);
  const [healthStatus, setHealthStatus] = useState<HealthHeartbeat[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        
        // Parallel fetch
        const [pnlRes, eventsRes, healthRes] = await Promise.all([
          supabase
            .from('pnl_daily')
            .select('*')
            .eq('instance_id', instanceId)
            .order('date', { ascending: true })
            .limit(30),
            
          supabase
            .from('audit_log')
            .select('*')
            .eq('instance_id', instanceId)
            .order('created_at', { ascending: false })
            .limit(10),
            
          supabase
            .from('health_heartbeat')
            .select('*')
            .eq('instance_id', instanceId)
        ]);

        if (pnlRes.data) setPnlHistory(pnlRes.data);
        if (eventsRes.data) setRecentEvents(eventsRes.data);
        if (healthRes.data) setHealthStatus(healthRes.data);
        
      } catch (error) {
        console.error('Error fetching dashboard data:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchData();

    // Realtime subscription for health
    const subscription = supabase
      .channel('dashboard_updates')
      .on('postgres_changes', { 
        event: '*', 
        schema: 'public', 
        table: 'health_heartbeat',
        filter: `instance_id=eq.${instanceId}`
      }, (payload) => {
        setHealthStatus(prev => {
           const newStatus = payload.new as HealthHeartbeat;
           const index = prev.findIndex(h => h.id === newStatus.id);
           if (index >= 0) {
             const updated = [...prev];
             updated[index] = newStatus;
             return updated;
           }
           return [...prev, newStatus];
        });
      })
      .subscribe();

    return () => {
      subscription.unsubscribe();
    };
  }, [instanceId]);

  return { pnlHistory, recentEvents, healthStatus, loading };
}
