import { useState, useEffect } from 'react';
import type { Database } from '../lib/types';
import { formatDate } from '../lib/utils';
import { BrainCircuit, Filter } from 'lucide-react';

type Thought = Database['public']['Tables']['thoughts']['Row'];

export default function Thoughts() {
  const [thoughts, setThoughts] = useState<Thought[]>([]);
  const [filterType, setFilterType] = useState<string>('all');

  useEffect(() => {
    // Mock fetch
    const fetchThoughts = async () => {
        // const { data } = await supabase...
        
        const mockThoughts: Thought[] = [
            { id: 'th1', instance_id: 'demo', content: 'SPY hitting 440 resistance, gamma flip level nearby.', type: 'scan', symbol: 'SPY', created_at: new Date(Date.now() - 1000 * 60 * 5).toISOString(), metadata: {} },
            { id: 'th2', instance_id: 'demo', content: 'Entered NVDA short put based on support hold.', type: 'entry', symbol: 'NVDA', created_at: new Date(Date.now() - 1000 * 60 * 60).toISOString(), metadata: {} },
            { id: 'th3', instance_id: 'demo', content: 'Looking for weakness in Tech due to yield spike.', type: 'general', symbol: null, created_at: new Date(Date.now() - 1000 * 60 * 120).toISOString(), metadata: {} },
            { id: 'th4', instance_id: 'demo', content: 'Health monitor: API latency spiked to 500ms.', type: 'health', symbol: null, created_at: new Date(Date.now() - 1000 * 60 * 180).toISOString(), metadata: {} },
        ];
        
        setThoughts(mockThoughts);
    };

    fetchThoughts();
  }, []);

  const filteredThoughts = filterType === 'all' 
    ? thoughts 
    : thoughts.filter(t => t.type === filterType);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <BrainCircuit className="w-6 h-6 text-brand" /> System Thoughts
        </h2>
        <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-text-secondary" />
            <select 
                value={filterType} 
                onChange={e => setFilterType(e.target.value)}
                className="bg-surface border border-border rounded text-sm text-white px-2 py-1 outline-none focus:border-brand"
            >
                <option value="all">All Types</option>
                <option value="scan">Scan</option>
                <option value="entry">Entry</option>
                <option value="exit">Exit</option>
                <option value="health">Health</option>
                <option value="general">General</option>
            </select>
        </div>
      </div>

      <div className="space-y-4 max-w-3xl">
          {filteredThoughts.length > 0 ? filteredThoughts.map(thought => (
              <div key={thought.id} className="bg-surface border border-border rounded-lg p-4 flex gap-4">
                  <div className="flex-shrink-0 pt-1">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold uppercase
                        ${thought.type === 'entry' ? 'bg-blue-500/20 text-blue-400' :
                          thought.type === 'exit' ? 'bg-purple-500/20 text-purple-400' :
                          thought.type === 'scan' ? 'bg-yellow-500/20 text-yellow-400' :
                          thought.type === 'health' ? 'bg-red-500/20 text-red-400' :
                          'bg-surface-highlight text-text-secondary'}
                      `}>
                          {thought.type[0]}
                      </div>
                  </div>
                  <div className="flex-1">
                      <div className="flex justify-between items-start mb-1">
                          <div className="flex items-center gap-2">
                              {thought.symbol && <span className="font-bold text-white text-sm">{thought.symbol}</span>}
                              <span className="text-xs text-text-muted uppercase px-1.5 py-0.5 rounded bg-surface-highlight border border-border">{thought.type}</span>
                          </div>
                          <span className="text-xs text-text-secondary">{formatDate(thought.created_at)}</span>
                      </div>
                      <p className="text-text-primary text-sm leading-relaxed">{thought.content}</p>
                  </div>
              </div>
          )) : (
              <div className="text-center py-12 text-text-muted">No thoughts found.</div>
          )}
      </div>
    </div>
  );
}
