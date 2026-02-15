import { useCallback, useEffect, useState } from 'react';
import { supabase } from '../lib/supabaseClient';
import type { FeedItem } from '../lib/copilotTypes';

const PAGE_SIZE = 50;

/**
 * Unified feed hook — streams FeedItems from Supabase `zoe_events` via realtime.
 * Hardcoded filter: only trades, warnings/critical alerts, and system nudges.
 */
export function useCopilotFeed() {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Load initial batch
  const loadHistory = useCallback(async () => {
    try {
      setLoading(true);
      const { data, error } = await supabase
        .from('zoe_events')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(PAGE_SIZE);

      if (error) throw error;
      setItems((data as FeedItem[]) ?? []);
    } catch (err) {
      console.error('Error loading feed:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // Realtime subscription
  useEffect(() => {
    const channel = supabase
      .channel('zoe_events_feed')
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'zoe_events',
        },
        (payload) => {
          const newItem = payload.new as FeedItem;
          setItems(prev => [newItem, ...prev].slice(0, 200));
        },
      )
      .subscribe();

    return () => {
      channel.unsubscribe();
    };
  }, []);

  // Hardcoded filter: trades, critical/warning alerts, system nudges
  const filteredItems = items.filter(item => {
    if (item.source === 'trade') return true;
    if (item.severity === 'critical' || item.severity === 'warning') return true;
    if (item.source === 'system') return true;
    return false;
  });

  return {
    items: filteredItems,
    loading,
    reload: loadHistory,
  };
}
