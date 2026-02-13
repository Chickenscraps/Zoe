import { useEffect, useState } from 'react';
import { supabase } from '../lib/supabaseClient';
import type { Database } from '../lib/types';

type Trade = Database['public']['Tables']['trades']['Row'];

export function useTrades(instanceId: string = 'primary-v4-live') {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchTrades() {
      try {
        setLoading(true);
        setError(null);
        const { data, error } = await supabase
          .from('trades')
          .select('*')
          .eq('instance_id', instanceId)
          .order('closed_at', { ascending: false });

        if (error) throw error;
        if (data) setTrades(data);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        console.error('Error fetching trades:', msg);
        setError(msg);
      } finally {
        setLoading(false);
      }
    }

    fetchTrades();
  }, [instanceId]);

  return { trades, loading, error };
}
