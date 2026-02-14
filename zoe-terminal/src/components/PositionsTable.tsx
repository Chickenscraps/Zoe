import { useMemo } from 'react';
import type { ColumnDef } from '@tanstack/react-table';
import { DataTable } from './DataTable';
import { formatCurrency, formatPercentage } from '../lib/utils';
import { useDashboardData } from '../hooks/useDashboardData';
import { FEE_RATE_PER_SIDE } from '../lib/constants';
import { Briefcase } from 'lucide-react';

interface PositionRow {
  symbol: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  market_value: number;
  pnl_percent: number;
  unrealized_pnl: number;
  portfolio_pct: number;
}

interface PositionsTableProps {
  /** Hide the section header — useful when embedding inside another card */
  hideHeader?: boolean;
  className?: string;
}

export function PositionsTable({ hideHeader, className }: PositionsTableProps) {
  const { holdingsRows, livePrices, cryptoFills } = useDashboardData();

  // Build position rows from holdings + live prices
  const positions = useMemo<PositionRow[]>(() => {
    if (!holdingsRows || holdingsRows.length === 0) return [];

    // Compute avg price from fills (include fees in cost basis)
    const avgPrices: Record<string, { totalCost: number; totalQty: number }> = {};
    for (const fill of (cryptoFills || [])) {
      if (fill.side === 'buy') {
        const sym = fill.symbol;
        if (!avgPrices[sym]) avgPrices[sym] = { totalCost: 0, totalQty: 0 };
        avgPrices[sym].totalCost += fill.qty * fill.price + (fill.fee || 0);
        avgPrices[sym].totalQty += fill.qty;
      }
    }

    // Map live prices by symbol
    const priceMap: Record<string, number> = {};
    for (const scan of (livePrices || [])) {
      const info = scan.info as any ?? {};
      if (info.mid) priceMap[scan.symbol] = info.mid;
    }

    // First pass: compute market values for portfolio % calculation
    const rows = holdingsRows.map(h => {
      const avg = avgPrices[h.asset] ? avgPrices[h.asset].totalCost / avgPrices[h.asset].totalQty : 0;
      const current = priceMap[h.asset] ?? (avg > 0 ? avg : 0);
      const mktVal = h.qty * current;
      const cost = h.qty * avg;
      const exitFee = mktVal * FEE_RATE_PER_SIDE;
      const pnl = avg > 0 ? mktVal - cost - exitFee : 0;
      const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0;

      return {
        symbol: h.asset,
        quantity: h.qty,
        avg_price: avg,
        current_price: current,
        market_value: mktVal,
        pnl_percent: isFinite(pnlPct) ? pnlPct : 0,
        unrealized_pnl: isFinite(pnl) ? pnl : 0,
        portfolio_pct: 0, // computed below
      };
    });

    const totalMktVal = rows.reduce((s, r) => s + r.market_value, 0);
    for (const r of rows) {
      r.portfolio_pct = totalMktVal > 0 ? (r.market_value / totalMktVal) * 100 : 0;
    }
    return rows;
  }, [holdingsRows, livePrices, cryptoFills]);

  const columns = useMemo<ColumnDef<PositionRow>[]>(() => [
    {
      header: 'Symbol',
      accessorKey: 'symbol',
      cell: info => <span className="font-semibold text-earth-700">{info.getValue() as string}</span>
    },
    {
      header: 'Qty',
      accessorKey: 'quantity',
      cell: info => <span className="text-text-secondary tabular-nums">{(info.getValue() as number).toFixed(6)}</span>
    },
    {
      header: 'Avg Price',
      accessorKey: 'avg_price',
      cell: info => {
        const val = info.getValue() as number;
        return val > 0
          ? <span className="tabular-nums">{formatCurrency(val)}</span>
          : <span className="text-text-dim">&mdash;</span>;
      }
    },
    {
      header: 'Price (USD)',
      accessorKey: 'current_price',
      cell: info => <span className="tabular-nums">{formatCurrency(info.getValue() as number)}</span>
    },
    {
      header: 'Value (USD)',
      accessorKey: 'market_value',
      cell: info => <span className="text-text-primary font-medium tabular-nums">{formatCurrency(info.getValue() as number)}</span>
    },
    {
      header: '% of Portfolio',
      accessorKey: 'portfolio_pct',
      cell: info => {
        const val = info.getValue() as number;
        return <span className="text-text-secondary tabular-nums">{val.toFixed(1)}%</span>;
      }
    },
    {
      header: 'P&L (%)',
      accessorKey: 'pnl_percent',
      cell: info => {
        const val = info.getValue() as number;
        const row = info.row.original;
        if (row.avg_price <= 0) return <span className="text-text-dim">&mdash;</span>;
        return (
          <span className={val >= 0 ? "text-profit tabular-nums" : "text-loss tabular-nums"}>
            {formatPercentage(val)}
          </span>
        );
      }
    },
    {
      header: 'P&L ($)',
      accessorKey: 'unrealized_pnl',
      cell: info => {
        const val = info.getValue() as number;
        const row = info.row.original;
        if (row.avg_price <= 0) return <span className="text-text-dim">&mdash;</span>;
        return (
          <span className={val >= 0 ? "text-profit tabular-nums" : "text-loss tabular-nums"}>
            {formatCurrency(val)}
          </span>
        );
      }
    }
  ], []);

  return (
    <div className={className}>
      {!hideHeader && (
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted flex items-center gap-2">
            <Briefcase className="w-3 h-3 text-profit" /> Open Positions
          </h3>
          <span className="text-[9px] font-bold text-text-dim uppercase tracking-widest">
            {positions.length} active
          </span>
        </div>
      )}

      {positions.length > 0 ? (
        <DataTable
          columns={columns}
          data={positions}
          emptyMessage="No open positions"
        />
      ) : (
        <div className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] p-8 text-center">
          <p className="text-text-dim text-xs">No open positions</p>
          <p className="text-text-dim/60 text-[9px] mt-1">Positions will appear when the bot executes trades</p>
        </div>
      )}
    </div>
  );
}
