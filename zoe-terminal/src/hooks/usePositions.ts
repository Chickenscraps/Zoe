import { useEffect, useState } from 'react';
import { supabase } from '../lib/supabaseClient';
import type { Database } from '../lib/types';

type PositionReportItem = Database['public']['Functions']['get_positions_report']['Returns'][0];

export function usePositions(accountId?: string) {
  const [positions, setPositions] = useState<PositionReportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchPositions() {
      try {
        setLoading(true);
        setError(null);
        const { data, error } = await supabase.rpc('get_positions_report' as any, {
            p_account_id: accountId,
        } as any);

        if (error) throw error;
        if (data) setPositions(data);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        console.error('Error fetching positions:', msg);
        setError(msg);
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
      }, () => {
        fetchPositions();
      })
      .subscribe();

    return () => {
      supabase.removeChannel(subscription);
    };
  }, [accountId]);

  return { positions, loading, error };
}
