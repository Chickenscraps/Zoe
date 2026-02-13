import { useState, useEffect } from 'react';
import type { Database } from '../lib/types';
import { formatDate } from '../lib/utils';
import { BrainCircuit, Filter } from 'lucide-react';
import { supabase } from '../lib/supabaseClient';
import { useModeContext } from '../lib/mode';

type Thought = Database['public']['Tables']['thoughts']['Row'];

const TYPE_CONFIG: Record<string, { bg: string; text: string; label: string }> = {
  scan:        { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: 'Scan' },
  signal:      { bg: 'bg-profit/20',     text: 'text-profit',     label: 'Signal' },
  paper_trade: { bg: 'bg-blue-500/20',   text: 'text-blue-400',   label: 'Paper' },
  order:       { bg: 'bg-profit/20',     text: 'text-profit',     label: 'Order' },
  order_error: { bg: 'bg-loss/20',       text: 'text-loss',       label: 'Error' },
  entry:       { bg: 'bg-blue-500/20',   text: 'text-blue-400',   label: 'Entry' },
  exit:        { bg: 'bg-purple-500/20', text: 'text-purple-400', label: 'Exit' },
  health:      { bg: 'bg-red-500/20',    text: 'text-red-400',    label: 'Health' },
  general:     { bg: 'bg-surface-highlight', text: 'text-text-secondary', label: 'General' },
};

export default function Thoughts() {
  const { mode } = useModeContext();
  const [thoughts, setThoughts] = useState<Thought[]>([]);
  const [filterType, setFilterType] = useState<string>('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchThoughts = async () => {
        try {
            setLoading(true);
            const { data, error } = await supabase
                .from('thoughts')
                .select('*')
                .eq('mode', mode)
                .order('created_at', { ascending: false })
                .limit(50);

            if (error) throw error;
            if (data) setThoughts(data);
        } catch (err) {
            console.error('Error fetching thoughts:', err);
        } finally {
            setLoading(false);
        }
    };

    fetchThoughts();
    const interval = setInterval(fetchThoughts, 15000); // refresh every 15s
    return () => clearInterval(interval);
  }, [mode]);

  const filteredThoughts = filterType === 'all'
    ? thoughts
    : thoughts.filter(t => t.type === filterType);

  // Get unique types from actual data for the filter dropdown
  const availableTypes = Array.from(new Set(thoughts.map(t => t.type))).sort();

  if (loading) {
    return (
        <div className="space-y-6">
            <h2 className="text-xl font-semibold text-white flex items-center gap-2">
                <BrainCircuit className="w-6 h-6 text-brand" /> System Thoughts
            </h2>
            <div className="text-text-secondary animate-pulse py-12">Consulting system memory...</div>
        </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-white flex items-center gap-2">
            <BrainCircuit className="w-6 h-6 text-brand" /> System Thoughts
            <span className="text-xs text-text-muted ml-2">({filteredThoughts.length})</span>
        </h2>
        <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-text-secondary" />
            <select
                value={filterType}
                onChange={e => setFilterType(e.target.value)}
                className="bg-surface border border-border rounded text-sm text-white px-2 py-1 outline-none focus:border-brand"
                title="Filter by type"
            >
                <option value="all">All Types</option>
                {availableTypes.map(type => (
                    <option key={type} value={type}>
                        {TYPE_CONFIG[type]?.label ?? type}
                    </option>
                ))}
            </select>
        </div>
      </div>

      <div className="space-y-3 max-w-3xl">
          {filteredThoughts.length > 0 ? filteredThoughts.map(thought => {
              const config = TYPE_CONFIG[thought.type] ?? TYPE_CONFIG.general;
              return (
              <div key={thought.id} className="bg-surface border border-border rounded-lg p-4 flex gap-4">
                  <div className="flex-shrink-0 pt-1">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold uppercase ${config.bg} ${config.text}`}>
                          {thought.type[0].toUpperCase()}
                      </div>
                  </div>
                  <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-start mb-1 gap-2">
                          <div className="flex items-center gap-2 flex-wrap">
                              {thought.symbol && <span className="font-bold text-white text-sm">{thought.symbol}</span>}
                              <span className={`text-xs uppercase px-1.5 py-0.5 rounded border border-border font-bold ${config.text} ${config.bg}`}>
                                  {config.label}
                              </span>
                          </div>
                          <span className="text-xs text-text-secondary whitespace-nowrap">{formatDate(thought.created_at)}</span>
                      </div>
                      <p className="text-text-primary text-sm leading-relaxed break-words">{thought.content}</p>
                  </div>
              </div>
              );
          }) : (
              <div className="text-center py-12 text-text-muted">No thoughts found.</div>
          )}
      </div>
    </div>
  );
}
