import { useEffect, useState } from 'react';
import { supabase } from '../lib/supabaseClient';
import type { Database } from '../lib/types';

type Position = Database['public']['Tables']['positions']['Row'];

export function usePositions(instanceId: string = 'primary-v4-live') {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchPositions() {
      try {
        setLoading(true);
        const { data, error } = await supabase
          .from('positions')
          .select('*')
          .eq('instance_id', instanceId)
          .eq('status', 'open') // Assuming we only want open positions
          .order('opened_at', { ascending: false });

        if (error) throw error;
        if (data) setPositions(data);
      } catch (err) {
        console.error('Error fetching positions:', err);
      } finally {
        setLoading(false);
      }
    }

    fetchPositions();

    const subscription = supabase
      .channel('positions_updates')
      .on('postgres_changes', { 
        event: '*', 
        schema: 'public', 
        table: 'positions',
        filter: `instance_id=eq.${instanceId}`
      }, (_payload) => {
        // Simple reload or manual merge. Manual merge for smoother UX.
        fetchPositions(); 
      })
      .subscribe();

    return () => {
      subscription.unsubscribe();
    };
  }, [instanceId]);

  return { positions, loading };
}
