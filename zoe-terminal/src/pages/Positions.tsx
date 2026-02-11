import { DataTable } from '../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import { useMemo } from 'react';
import { formatCurrency, formatPercentage } from '../lib/utils';

interface PositionRow {
  symbol: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  market_value: number;
  pnl_percent: number;
  unrealized_pnl: number;
}

// Blank placeholder row
const EMPTY_POSITIONS: PositionRow[] = [
  {
    symbol: '--',
    quantity: 0,
    avg_price: 0,
    current_price: 0,
    market_value: 0,
    pnl_percent: 0,
    unrealized_pnl: 0,
  },
];

export default function Positions() {
  const columns = useMemo<ColumnDef<PositionRow>[]>(() => [
    {
      header: 'Symbol',
      accessorKey: 'symbol',
      cell: info => <span className="font-semibold text-white">{info.getValue() as string}</span>
    },
    {
      header: 'Qty',
      accessorKey: 'quantity',
      cell: info => <span className="text-text-secondary">{info.getValue() as number}</span>
    },
    {
      header: 'Avg Price',
      accessorKey: 'avg_price',
      cell: info => formatCurrency(info.getValue() as number)
    },
    {
      header: 'Current Mark',
      accessorKey: 'current_price',
      cell: info => formatCurrency(info.getValue() as number)
    },
    {
        header: 'Market Value',
        accessorKey: 'market_value',
        cell: info => <span className="text-text-primary font-medium">{formatCurrency(info.getValue() as number)}</span>
    },
    {
      header: 'P&L (%)',
      accessorKey: 'pnl_percent',
      cell: info => {
        const val = info.getValue() as number;
        return (
          <span className={val >= 0 ? "text-profit" : "text-loss"}>
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
          <span className={val >= 0 ? "text-profit" : "text-loss"}>
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
            0 active trades
         </div>
      </div>

      <DataTable
        columns={columns}
        data={EMPTY_POSITIONS}
      />
    </div>
  );
}
