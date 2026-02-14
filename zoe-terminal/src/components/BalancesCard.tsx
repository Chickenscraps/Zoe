import { useMemo } from 'react';
import { Wallet } from 'lucide-react';
import { formatCurrency, cn } from '../lib/utils';
import type { Database } from '../lib/types';

type FocusSnapshot = Database['public']['Tables']['market_snapshot_focus']['Row'];
type CryptoPosition = Database['public']['Tables']['crypto_positions']['Row'];

interface BalancesCardProps {
  cashUsd: number;
  positions: CryptoPosition[];
  focusSnapshots: Record<string, FocusSnapshot>;
  className?: string;
}

interface AssetRow {
  asset: string;
  qty: number;
  price: number;
  value: number;
  allocation: number;
}

export function BalancesCard({ cashUsd, positions, focusSnapshots, className }: BalancesCardProps) {
  const { assets, totalValue } = useMemo(() => {
    const rows: AssetRow[] = [];
    let cryptoTotal = 0;

    for (const pos of positions) {
      if (pos.qty <= 0) continue;
      const snap = focusSnapshots[pos.symbol];
      const price = snap?.mid ?? 0;
      const value = pos.qty * price;
      cryptoTotal += value;
      rows.push({
        asset: pos.symbol.replace('/USD', '').replace('-USD', ''),
        qty: pos.qty,
        price,
        value,
        allocation: 0, // computed below
      });
    }

    const total = cashUsd + cryptoTotal;

    // Compute allocations
    for (const row of rows) {
      row.allocation = total > 0 ? (row.value / total) * 100 : 0;
    }

    // Sort by value descending
    rows.sort((a, b) => b.value - a.value);

    return { assets: rows, totalValue: total };
  }, [cashUsd, positions, focusSnapshots]);

  const cashAllocation = totalValue > 0 ? (cashUsd / totalValue) * 100 : 100;

  return (
    <div className={cn('card-premium card-shimmer-sweep p-4 sm:p-6', className)}>
      <div className="flex items-center justify-between mb-3 sm:mb-4">
        <h3 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted flex items-center gap-2">
          <Wallet className="w-3 h-3 text-accent" /> Balance Breakdown
        </h3>
        <span className="text-[9px] font-bold text-text-dim uppercase tracking-widest">
          {formatCurrency(totalValue)} total
        </span>
      </div>

      <div className="space-y-2">
        {/* Cash row */}
        <div className="flex items-center justify-between py-1.5 px-2 bg-background/50 border border-border rounded-lg">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-black text-accent uppercase tracking-widest">USD</span>
            <span className="text-[9px] text-text-dim">Cash</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold text-white tabular-nums">{formatCurrency(cashUsd)}</span>
            <span className="text-[9px] text-text-dim tabular-nums w-12 text-right">
              {cashAllocation.toFixed(1)}%
            </span>
          </div>
        </div>

        {/* Crypto asset rows */}
        {assets.map((row) => (
          <div
            key={row.asset}
            className="flex items-center justify-between py-1.5 px-2 bg-background/50 border border-border rounded-lg"
          >
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-black text-white uppercase tracking-widest">{row.asset}</span>
              <span className="text-[9px] text-text-dim tabular-nums">
                {row.qty < 1 ? row.qty.toFixed(6) : row.qty.toFixed(4)}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs font-bold text-white tabular-nums">{formatCurrency(row.value)}</span>
              <span className="text-[9px] text-text-dim tabular-nums w-12 text-right">
                {row.allocation.toFixed(1)}%
              </span>
            </div>
          </div>
        ))}

        {assets.length === 0 && (
          <p className="text-[9px] text-text-dim text-center py-2">No crypto holdings</p>
        )}
      </div>
    </div>
  );
}
