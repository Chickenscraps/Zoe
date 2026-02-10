import { useTrades } from '../hooks/useTrades';
import { DataTable } from '../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import { useMemo } from 'react';
import type { Database } from '../lib/types';
import { formatCurrency, formatDate } from '../lib/utils';
import { useNavigate } from 'react-router-dom';

type Trade = Database['public']['Tables']['trades']['Row'];

export default function Trades() {
  const { trades, loading } = useTrades();
  const navigate = useNavigate();

  // Mock data if empty
  const displayTrades = trades.length > 0 ? trades : [
    { 
      trade_id: 't1', instance_id: 'demo', symbol: 'NVDA', strategy: 'Short Put',
      opened_at: '2023-09-15T10:00:00Z', closed_at: '2023-09-20T14:30:00Z',
      realized_pnl: 150, r_multiple: 0.5, outcome: 'win', rationale: 'Support hold'
    },
    { 
      trade_id: 't2', instance_id: 'demo', symbol: 'TSLA', strategy: 'Call Deploy',
      opened_at: '2023-09-18T10:00:00Z', closed_at: '2023-09-19T09:45:00Z',
      realized_pnl: -200, r_multiple: -1.0, outcome: 'loss', rationale: 'News fakeout'
    }
  ] as Trade[];

  const columns = useMemo<ColumnDef<Trade>[]>(() => [
    {
      header: 'Symbol',
      accessorKey: 'symbol',
      cell: info => <span className="font-bold text-white">{info.getValue() as string}</span>
    },
    {
      header: 'Strategy',
      accessorKey: 'strategy',
    },
    {
      header: 'Opened',
      accessorKey: 'opened_at',
      cell: info => <span className="text-text-secondary">{formatDate(info.getValue() as string)}</span>
    },
    {
      header: 'Closed',
      accessorKey: 'closed_at',
      cell: info => {
        const val = info.getValue() as string;
        return val ? <span className="text-text-secondary">{formatDate(val)}</span> : '-';
      }
    },
    {
      header: 'P&L',
      accessorKey: 'realized_pnl',
      cell: info => {
        const val = info.getValue() as number;
        return (
          <span className={val >= 0 ? "text-profit font-medium" : "text-loss font-medium"}>
            {formatCurrency(val)}
          </span>
        );
      }
    },
    {
      header: 'Outcome',
      accessorKey: 'outcome',
      cell: info => {
        const val = info.getValue() as string;
        return (
          <span className={`uppercase text-xs font-bold ${
            val === 'win' ? 'text-profit' : 
            val === 'loss' ? 'text-loss' : 'text-text-secondary'
          }`}>
            {val}
          </span>
        );
      }
    }
  ], []);

  if (loading) return <div className="text-text-secondary animate-pulse">Loading trades...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
         <h2 className="text-xl font-bold text-white">Trade History</h2>
         <div className="text-sm text-text-secondary">
            {displayTrades.length} closed trades
         </div>
      </div>
      
      <DataTable 
        columns={columns} 
        data={displayTrades} 
        onRowClick={(row) => navigate(`/trades/${row.trade_id}`)}
      />
    </div>
  );
}
