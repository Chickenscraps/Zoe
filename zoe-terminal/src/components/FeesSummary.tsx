import { useCallback, useEffect, useState } from 'react';
import { Receipt } from 'lucide-react';
import { formatCurrency, cn } from '../lib/utils';
import { supabase, supabaseMisconfigured } from '../lib/supabaseClient';
import { useModeContext } from '../lib/mode';

interface FeeBucket {
  label: string;
  amount: number;
}

interface FeesSummaryProps {
  className?: string;
}

export function FeesSummary({ className }: FeesSummaryProps) {
  const { mode } = useModeContext();
  const [buckets, setBuckets] = useState<FeeBucket[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchFees = useCallback(async () => {
    if (supabaseMisconfigured) return;
    try {
      const now = new Date();
      const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString();
      const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString();
      const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString();

      const [todayRes, weekRes, monthRes, allRes] = await Promise.all([
        supabase
          .from('fee_ledger')
          .select('fee_usd')
          .eq('mode', mode)
          .gte('created_at', todayStart),
        supabase
          .from('fee_ledger')
          .select('fee_usd')
          .eq('mode', mode)
          .gte('created_at', weekAgo),
        supabase
          .from('fee_ledger')
          .select('fee_usd')
          .eq('mode', mode)
          .gte('created_at', monthAgo),
        supabase
          .from('fee_ledger')
          .select('fee_usd')
          .eq('mode', mode),
      ]);

      const sum = (rows: { fee_usd: number }[] | null) =>
        (rows ?? []).reduce((s, r) => s + (r.fee_usd ?? 0), 0);

      setBuckets([
        { label: 'Today', amount: sum(todayRes.data as any) },
        { label: '7d', amount: sum(weekRes.data as any) },
        { label: '30d', amount: sum(monthRes.data as any) },
        { label: 'All Time', amount: sum(allRes.data as any) },
      ]);
    } catch (err) {
      console.error('FeesSummary fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [mode]);

  useEffect(() => {
    fetchFees();
    const interval = setInterval(fetchFees, 30_000);
    return () => clearInterval(interval);
  }, [fetchFees]);

  if (loading) return null;

  const allTimeFees = buckets.find(b => b.label === 'All Time')?.amount ?? 0;
  if (allTimeFees === 0 && buckets.every(b => b.amount === 0)) return null;

  return (
    <div className={cn('card-premium card-shimmer-sweep p-4 sm:p-6', className)}>
      <div className="flex items-center justify-between mb-3 sm:mb-4">
        <h3 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted flex items-center gap-2">
          <Receipt className="w-3 h-3 text-warning" /> Trading Fees
        </h3>
      </div>

      <div className="grid grid-cols-4 gap-2">
        {buckets.map((b) => (
          <div key={b.label} className="text-center py-2 px-1 bg-background/50 border border-border rounded-lg">
            <p className="text-[9px] font-bold text-text-dim uppercase tracking-widest mb-1">{b.label}</p>
            <p className="text-xs font-bold text-warning tabular-nums">{formatCurrency(b.amount)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
