import { usePositions } from '../hooks/usePositions';
import { DataTable } from '../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import { useMemo } from 'react';
import type { Database } from '../lib/types';
import { formatCurrency, formatPercentage } from '../lib/utils';

type PositionReportItem = Database['public']['Functions']['get_positions_report']['Returns'][0];

export default function Positions() {
  const { positions, loading } = usePositions();

  const columns = useMemo<ColumnDef<PositionReportItem>[]>(() => [
    {
      header: 'Symbol',
      accessorKey: 'symbol',
      cell: info => <span className="font-bold text-white">{info.getValue() as string}</span>
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

  if (loading) return <div className="text-text-secondary animate-pulse p-8">Loading positions...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
         <h2 className="text-xl font-bold text-white">Open Positions</h2>
         <div className="text-sm text-text-secondary">
            {positions.length} active trades
         </div>
      </div>
      
      <DataTable 
        columns={columns} 
        data={positions} 
      />
    </div>
  );
}
