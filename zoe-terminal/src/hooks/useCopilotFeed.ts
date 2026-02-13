import { useCallback, useEffect, useRef, useState } from 'react';
import { supabase } from '../lib/supabaseClient';
import { useModeContext } from '../lib/mode';
import type { FeedItem, FeedFilter } from '../lib/copilotTypes';

const PAGE_SIZE = 50;
const THOUGHT_THROTTLE_MS = 2000;

/**
 * Unified feed hook — streams FeedItems from Supabase `zoe_events` via realtime.
 * Supports filtering by source, symbol, and severity.
 */
export function useCopilotFeed() {
  const { mode } = useModeContext();
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const lastThoughtTs = useRef(0);

  const [filter, setFilter] = useState<FeedFilter>({
    sources: new Set(['chat', 'thought', 'system', 'trade', 'config']),
    symbol: '',
    severity: 'all',
  });

  // Load initial batch
  const loadHistory = useCallback(async () => {
    try {
      setLoading(true);
      const { data, error } = await supabase
        .from('zoe_events')
        .select('*')
        .eq('mode', mode)
        .order('created_at', { ascending: false })
        .limit(PAGE_SIZE);

      if (error) throw error;
      setItems((data as FeedItem[]) ?? []);
    } catch (err) {
      console.error('Error loading feed:', err);
    } finally {
      setLoading(false);
    }
  }, [mode]);

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
          filter: `mode=eq.${mode}`,
        },
        (payload) => {
          const newItem = payload.new as FeedItem;

          // Thought throttle — skip thoughts arriving < 2s apart
          if (newItem.source === 'thought') {
            const now = Date.now();
            if (now - lastThoughtTs.current < THOUGHT_THROTTLE_MS) return;
            lastThoughtTs.current = now;
          }

          setItems(prev => [newItem, ...prev].slice(0, 200));
        },
      )
      .subscribe();

    return () => {
      channel.unsubscribe();
    };
  }, [mode]);

  // Apply filters
  const filteredItems = items.filter(item => {
    if (!filter.sources.has(item.source)) return false;
    if (filter.symbol && item.symbol !== filter.symbol) return false;
    if (filter.severity !== 'all' && item.severity !== filter.severity) return false;
    return true;
  });

  const updateFilter = useCallback((patch: Partial<FeedFilter>) => {
    setFilter(prev => ({ ...prev, ...patch }));
  }, []);

  const toggleSource = useCallback((source: FeedItem['source']) => {
    setFilter(prev => {
      const next = new Set(prev.sources);
      if (next.has(source)) {
        next.delete(source);
      } else {
        next.add(source);
      }
      return { ...prev, sources: next };
    });
  }, []);

  return {
    items: filteredItems,
    allItems: items,
    loading,
    filter,
    updateFilter,
    toggleSource,
    reload: loadHistory,
  };
}
