import { useEffect, useState } from 'react';
import { supabase } from '../lib/supabaseClient';
import type { Database } from '../lib/types';

type HealthHeartbeat = Database['public']['Tables']['health_heartbeat']['Row'];
type AccountOverview = Database['public']['Functions']['get_account_overview']['Returns'][0];
type ActivityFeedItem = Database['public']['Functions']['get_activity_feed']['Returns'][0];

export function useDashboardData(discordId: string = '292890243852664855') {
  const [accountOverview, setAccountOverview] = useState<AccountOverview | null>(null);
  const [recentEvents, setRecentEvents] = useState<ActivityFeedItem[]>([]);
  const [healthStatus, setHealthStatus] = useState<HealthHeartbeat[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        
        // Parallel fetch using RPCs
        const [overviewRes, feedRes, healthRes] = await Promise.all([
          supabase.rpc('get_account_overview' as any, { p_discord_id: discordId } as any),
          supabase.rpc('get_activity_feed' as any, { p_limit: 10 } as any),
          supabase
            .from('health_heartbeat')
            .select('*')
        ]) as any[];

        if (overviewRes.data && overviewRes.data.length > 0) {
            setAccountOverview(overviewRes.data[0]);
        }
        if (feedRes.data) setRecentEvents(feedRes.data);
        if (healthRes.data) setHealthStatus(healthRes.data);
        
      } catch (error) {
        console.error('Error fetching dashboard data:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchData();

    // Realtime subscription for health (simple table list)
    const subscription = supabase
      .channel('dashboard_updates')
      .on('postgres_changes', { 
        event: '*', 
        schema: 'public', 
        table: 'health_heartbeat'
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
  }, [discordId]);

  return { accountOverview, recentEvents, healthStatus, loading };
}
