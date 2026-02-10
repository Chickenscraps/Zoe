import { useEffect, useState } from 'react';
import { supabase } from '../lib/supabaseClient';
import type { Database } from '../lib/types';

type PositionReportItem = Database['public']['Functions']['get_positions_report']['Returns'][0];

export function usePositions(accountId?: string) {
  const [positions, setPositions] = useState<PositionReportItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchPositions() {
      try {
        setLoading(true);
        const { data, error } = await supabase.rpc('get_positions_report' as any, { 
            p_account_id: accountId 
        } as any);

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
        table: 'positions'
      }, () => {
        fetchPositions(); 
      })
      .subscribe();

    return () => {
      subscription.unsubscribe();
    };
  }, [accountId]);

  return { positions, loading };
}
