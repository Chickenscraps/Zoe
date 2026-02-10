import { useState, useEffect } from 'react';
import type { Database } from '../lib/types';
import { Target, Zap } from 'lucide-react';

type CandidateScan = Database['public']['Tables']['candidate_scans']['Row'];

export default function Scanner() {
  const [candidates, setCandidates] = useState<CandidateScan[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Mock fetch for now, or real if available
    const fetchCandidates = async () => {
        setLoading(true);
        // const { data } = await supabase.from('candidate_scans')...
        
        // Mock data
        const mockData: CandidateScan[] = [
            {
                id: 'c1', instance_id: 'demo', symbol: 'AMZN', score: 85,
                score_breakdown: { trend: 30, value: 25, volatility: 30 },
                info: { ivr: 45, liquidity: 'high', catalyst: 'earnings', sector: 'tech' },
                recommended_strategy: 'Short Put Vertical',
                created_at: new Date().toISOString()
            },
            {
                id: 'c2', instance_id: 'demo', symbol: 'GOOGL', score: 72,
                score_breakdown: { trend: 20, value: 30, volatility: 22 },
                info: { ivr: 32, liquidity: 'high', catalyst: 'none', sector: 'tech' },
                recommended_strategy: 'Iron Condor',
                created_at: new Date().toISOString()
            },
            {
                id: 'c3', instance_id: 'demo', symbol: 'AMD', score: 91,
                score_breakdown: { trend: 35, value: 26, volatility: 30 },
                info: { ivr: 55, liquidity: 'high', catalyst: 'product launch', sector: 'semi' },
                recommended_strategy: 'Long Call',
                created_at: new Date().toISOString()
            }
        ];
        
        setCandidates(mockData);
        setLoading(false);
    };

    fetchCandidates();
  }, []);

  if (loading) return <div className="text-text-secondary animate-pulse">Scanning market...</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
          <h2 className="text-xl font-bold text-white">Market Scanner</h2>
          <div className="bg-surface-highlight/50 px-3 py-1 rounded text-xs text-text-secondary">
              Last scan: just now
          </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {candidates.map(candidate => (
              <div key={candidate.id} className="bg-surface border border-border rounded-lg p-5 hover:border-brand/30 transition-colors">
                  <div className="flex justify-between items-start mb-4">
                      <div>
                          <h3 className="text-2xl font-bold text-white">{candidate.symbol}</h3>
                          <div className="flex gap-2 text-xs text-text-muted mt-1">
                              <span className="uppercase">{(candidate.info as any).sector}</span>
                              <span>•</span>
                              <span className="uppercase">IVR {(candidate.info as any).ivr}</span>
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
                               <div className="h-full bg-blue-500" style={{ width: `${((candidate.score_breakdown as any).trend / 35) * 100}%` }} />
                           </div>
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                          <span className="w-16 text-text-muted">Value</span>
                           <div className="flex-1 h-1.5 bg-surface-highlight rounded-full overflow-hidden">
                               <div className="h-full bg-emerald-500" style={{ width: `${((candidate.score_breakdown as any).value / 35) * 100}%` }} />
                           </div>
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                          <span className="w-16 text-text-muted">Vol</span>
                           <div className="flex-1 h-1.5 bg-surface-highlight rounded-full overflow-hidden">
                               <div className="h-full bg-purple-500" style={{ width: `${((candidate.score_breakdown as any).volatility / 35) * 100}%` }} />
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
                      
                      { (candidate.info as any).catalyst && (candidate.info as any).catalyst !== 'none' && (
                          <div className="flex justify-between items-center text-sm">
                              <span className="text-text-secondary flex items-center gap-1">
                                  <Zap className="w-3 h-3 text-warning" /> Catalyst
                              </span>
                              <span className="text-warning capitalize">{(candidate.info as any).catalyst}</span>
                          </div>
                      )}
                  </div>
              </div>
          ))}
      </div>
    </div>
  );
}
