import { useState, useEffect } from 'react';
import type { Database } from '../lib/types';
import { Target, Zap } from 'lucide-react';
import { supabase } from '../lib/supabaseClient';

type CandidateScan = Database['public']['Tables']['candidate_scans']['Row'];

export default function Scanner() {
  const [candidates, setCandidates] = useState<CandidateScan[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchCandidates = async () => {
        try {
            setLoading(true);
            const { data, error } = await supabase
                .from('candidate_scans')
                .select('*')
                .order('created_at', { ascending: false })
                .limit(12);
            
            if (error) throw error;
            if (data) setCandidates(data);
        } catch (err) {
            console.error('Error fetching candidates:', err);
        } finally {
            setLoading(false);
        }
    };

    fetchCandidates();
  }, []);

  if (loading) return <div className="text-text-secondary animate-pulse p-8">Scanning market...</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
          <h2 className="text-xl font-bold text-white">Market Scanner</h2>
          <div className="bg-surface-highlight/50 px-3 py-1 rounded text-xs text-text-secondary">
              Real-time Analysis
          </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {candidates.length > 0 ? candidates.map(candidate => (
              <div key={candidate.id} className="bg-surface border border-border rounded-lg p-5 hover:border-brand/30 transition-colors">
                  <div className="flex justify-between items-start mb-4">
                      <div>
                          <h3 className="text-2xl font-bold text-white">{candidate.symbol}</h3>
                          <div className="flex gap-2 text-xs text-text-muted mt-1">
                              <span className="uppercase">{(candidate.info as any)?.sector ?? 'N/A'}</span>
                              <span>•</span>
                              <span className="uppercase">IVR {(candidate.info as any)?.ivr ?? 'N/A'}</span>
                          </div>
                      </div>
                      <div className="flex flex-col items-end">
                          <div className="text-3xl font-bold text-brand">{candidate.score}</div>
                          <div className="text-[10px] text-text-secondary uppercase tracking-wider">Score</div>
                      </div>
                  </div>

                  {/* Score Bars */}
                  <div className="space-y-2 mb-4">
                      <div className="flex items-center gap-2 text-xs">
                          <span className="w-16 text-text-muted">Trend</span>
                           <div className="flex-1 h-1.5 bg-surface-highlight rounded-full overflow-hidden">
                               <div className="h-full bg-blue-500" style={{ width: `${((candidate.score_breakdown as any)?.trend ?? 0) / 35 * 100}%` }} />
                           </div>
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                          <span className="w-16 text-text-muted">Value</span>
                           <div className="flex-1 h-1.5 bg-surface-highlight rounded-full overflow-hidden">
                               <div className="h-full bg-emerald-500" style={{ width: `${((candidate.score_breakdown as any)?.value ?? 0) / 35 * 100}%` }} />
                           </div>
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                          <span className="w-16 text-text-muted">Vol</span>
                           <div className="flex-1 h-1.5 bg-surface-highlight rounded-full overflow-hidden">
                               <div className="h-full bg-purple-500" style={{ width: `${((candidate.score_breakdown as any)?.volatility ?? 0) / 35 * 100}%` }} />
                           </div>
                      </div>
                  </div>

                  <div className="pt-4 border-t border-border space-y-3">
                      <div className="flex justify-between items-center text-sm">
                          <span className="text-text-secondary flex items-center gap-1">
                              <Target className="w-3 h-3" /> Strategy
                          </span>
                          <span className="text-white font-medium">{candidate.recommended_strategy}</span>
                      </div>
                      
                      { (candidate.info as any)?.catalyst && (candidate.info as any)?.catalyst !== 'none' && (
                          <div className="flex justify-between items-center text-sm">
                              <span className="text-text-secondary flex items-center gap-1">
                                  <Zap className="w-3 h-3 text-warning" /> Catalyst
                              </span>
                              <span className="text-warning capitalize">{(candidate.info as any).catalyst}</span>
                          </div>
                      )}
                  </div>
              </div>
          )) : (
              <div className="col-span-full text-center py-12 text-text-muted italic border border-dashed border-border rounded-lg">
                  No scan candidates found for current regime.
              </div>
          )}
      </div>
    </div>
  );
}
