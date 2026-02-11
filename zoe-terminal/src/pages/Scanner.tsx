import { useState, useEffect } from 'react';
import type { Database } from '../lib/types';
import { Target, Zap, Activity } from 'lucide-react';
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
    <div className="space-y-10">
      <div className="flex justify-between items-end border-b border-border pb-8">
          <div>
            <h2 className="text-3xl font-semibold text-white tracking-tighter">Market Scanner</h2>
            <p className="text-sm text-text-muted mt-2 font-medium tracking-tight">Autonomous candidate analysis across multiple regimes.</p>
          </div>
          <div className="bg-surface-highlight/50 px-4 py-2 rounded-xl border border-border text-[10px] font-semibold text-white uppercase tracking-[0.2em]">
              Real-time Active
          </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {candidates.length > 0 ? candidates.map(candidate => (
              <div key={candidate.id} className="card-premium p-8 group overflow-hidden relative">
                  {/* Subtle Background Accent */}
                  <div className="absolute top-0 right-0 w-32 h-32 bg-white/[0.02] rounded-full -mr-16 -mt-16 transition-all group-hover:bg-white/[0.05]" />
                  
                  <div className="flex justify-between items-start mb-8 relative z-10 min-w-0">
                      <div>
                          <h3 className="text-3xl font-semibold text-white tracking-tighter">{candidate.symbol}</h3>
                          <div className="flex gap-2 text-[10px] text-text-muted mt-2 font-semibold uppercase tracking-widest">
                              <span className="text-white/40">{(candidate.info as any)?.sector ?? 'N/A'}</span>
                              <span className="opacity-30">•</span>
                              <span className="text-white/40">IVR {(candidate.info as any)?.ivr ?? 'N/A'}</span>
                          </div>
                      </div>
                      <div className="flex flex-col items-end">
                          <div className="text-4xl font-semibold text-white tracking-tighter tabular-nums">{candidate.score}</div>
                          <div className="text-[10px] text-text-muted font-semibold uppercase tracking-[0.2em] mt-1">Refined Score</div>
                      </div>
                  </div>

                  {/* Score Bars */}
                  <div className="space-y-3 mb-8 relative z-10">
                      <div className="flex items-center gap-3 text-[10px] font-semibold uppercase tracking-widest">
                          <span className="w-16 text-text-muted">Trend</span>
                           <div className="flex-1 h-1.5 bg-background shadow-crisp rounded-full overflow-hidden">
                               <div className="h-full bg-white opacity-80" style={{ width: `${((candidate.score_breakdown as any)?.trend ?? 0) / 35 * 100}%` }} />
                           </div>
                      </div>
                      <div className="flex items-center gap-3 text-[10px] font-semibold uppercase tracking-widest">
                          <span className="w-16 text-text-muted">Value</span>
                           <div className="flex-1 h-1.5 bg-background shadow-crisp rounded-full overflow-hidden">
                               <div className="h-full bg-profit" style={{ width: `${((candidate.score_breakdown as any)?.value ?? 0) / 35 * 100}%` }} />
                           </div>
                      </div>
                      <div className="flex items-center gap-3 text-[10px] font-semibold uppercase tracking-widest">
                          <span className="w-16 text-text-muted">Regime</span>
                           <div className="flex-1 h-1.5 bg-background shadow-crisp rounded-full overflow-hidden">
                               <div className="h-full bg-white opacity-40" style={{ width: `${((candidate.score_breakdown as any)?.volatility ?? 0) / 35 * 100}%` }} />
                           </div>
                      </div>
                  </div>

                  <div className="pt-6 border-t border-border/50 space-y-4 relative z-10">
                      <div className="flex justify-between items-center text-xs">
                          <span className="text-text-muted font-semibold uppercase tracking-widest flex items-center gap-2">
                              <Target className="w-3 h-3 text-profit" /> Recommended Strategy
                          </span>
                          <span className="text-white font-semibold uppercase tracking-tight">{candidate.recommended_strategy}</span>
                      </div>
                      
                      { (candidate.info as any)?.catalyst && (candidate.info as any)?.catalyst !== 'none' && (
                          <div className="flex justify-between items-center text-xs">
                              <span className="text-text-muted font-semibold uppercase tracking-widest flex items-center gap-2">
                                  <Zap className="w-3 h-3 text-warning" /> Catalyst Detected
                              </span>
                              <span className="text-warning font-semibold uppercase tracking-tight">{(candidate.info as any).catalyst}</span>
                          </div>
                      )}
                  </div>
              </div>
          )) : (
              <div className="col-span-full text-center py-20 text-text-muted italic border border-dashed border-border/50 rounded-cards bg-surface/50">
                  <Activity className="w-8 h-8 text-border mx-auto mb-4 opacity-50" />
                  No scan candidates found for current regime.
              </div>
          )}
      </div>
    </div>
  );
}
