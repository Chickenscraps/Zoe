import { DataTable } from '../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import { useMemo } from 'react';
import { formatCurrency, formatPercentage } from '../lib/utils';
import { useDashboardData } from '../hooks/useDashboardData';
import { FEE_RATE_PER_SIDE } from '../lib/constants';

interface PositionRow {
  symbol: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  market_value: number;
  pnl_percent: number;
  unrealized_pnl: number;
}

export default function Positions() {
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

    return holdingsRows.map(h => {
      const avg = avgPrices[h.asset] ? avgPrices[h.asset].totalCost / avgPrices[h.asset].totalQty : 0;
      const current = priceMap[h.asset] ?? avg;
      const mktVal = h.qty * current;
      const cost = h.qty * avg;
      const exitFee = mktVal * FEE_RATE_PER_SIDE; // estimated exit fee
      const pnl = mktVal - cost - exitFee;
      const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0; // as percentage (e.g., -2.04 for -2.04%)

      return {
        symbol: h.asset,
        quantity: h.qty,
        avg_price: avg,
        current_price: current,
        market_value: mktVal,
        pnl_percent: pnlPct,
        unrealized_pnl: pnl,
      };
    });
  }, [holdingsRows, livePrices, cryptoFills]);

  const columns = useMemo<ColumnDef<PositionRow>[]>(() => [
    {
      header: 'Symbol',
      accessorKey: 'symbol',
      cell: info => <span className="font-semibold text-white">{info.getValue() as string}</span>
    },
    {
      header: 'Qty',
      accessorKey: 'quantity',
      cell: info => <span className="text-text-secondary tabular-nums">{(info.getValue() as number).toFixed(6)}</span>
    },
    {
      header: 'Avg Price',
      accessorKey: 'avg_price',
      cell: info => <span className="tabular-nums">{formatCurrency(info.getValue() as number)}</span>
    },
    {
      header: 'Current Mark',
      accessorKey: 'current_price',
      cell: info => <span className="tabular-nums">{formatCurrency(info.getValue() as number)}</span>
    },
    {
        header: 'Market Value',
        accessorKey: 'market_value',
        cell: info => <span className="text-text-primary font-medium tabular-nums">{formatCurrency(info.getValue() as number)}</span>
    },
    {
      header: 'P&L (%)',
      accessorKey: 'pnl_percent',
      cell: info => {
        const val = info.getValue() as number;
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
        return (
          <span className={val >= 0 ? "text-profit tabular-nums" : "text-loss tabular-nums"}>
            {formatCurrency(val)}
          </span>
        );
      }
    }
  ], []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
         <h2 className="text-xl font-semibold text-white">Open Positions</h2>
         <div className="text-sm text-text-secondary">
            {positions.length} active trade{positions.length !== 1 ? 's' : ''}
         </div>
      </div>

      {positions.length > 0 ? (
        <DataTable
          columns={columns}
          data={positions}
        />
      ) : (
        <div className="card-premium p-12 text-center">
          <p className="text-text-dim text-sm">No open positions</p>
          <p className="text-text-dim text-xs mt-1">Positions will appear when the bot executes trades</p>
        </div>
      )}
    </div>
  );
}
