import { usePositions } from '../hooks/usePositions';
import { DataTable } from '../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import { useMemo } from 'react';
import type { Database } from '../lib/types';
import { formatCurrency } from '../lib/utils';
import { StatusChip } from '../components/StatusChip';
import { AlertCircle } from 'lucide-react';

type Position = Database['public']['Tables']['positions']['Row'];

export default function Positions() {
  const { positions, loading } = usePositions();

  // Mock data if empty
  const displayPositions = positions.length > 0 ? positions : [
    { 
      id: '1', instance_id: 'demo', symbol: 'SPY', strategy: 'Short Put Vertical', 
      opened_at: '2023-10-01T10:00:00Z', dte: 25, short_delta: 0.16, ivr: 45, 
      credit_debit: 'credit', max_risk: 500, unrealized_pnl: 50, pct_to_tp: 10,
      warnings: [], status: 'open', entry_price: 1.20, current_mark: 1.10, qty: 1
    },
    { 
      id: '2', instance_id: 'demo', symbol: 'QQQ', strategy: 'Iron Condor', 
      opened_at: '2023-10-02T11:00:00Z', dte: 15, short_delta: 0.20, ivr: 60, 
      credit_debit: 'credit', max_risk: 800, unrealized_pnl: -120, pct_to_tp: -15,
      warnings: ['ITM'], status: 'open', entry_price: 2.50, current_mark: 2.80, qty: 2
    }
  ] as Position[];

  const columns = useMemo<ColumnDef<Position>[]>(() => [
    {
      header: 'Symbol',
      accessorKey: 'symbol',
      cell: info => <span className="font-bold text-white">{info.getValue() as string}</span>
    },
    {
      header: 'Strategy',
      accessorKey: 'strategy',
      cell: info => <span className="text-text-secondary">{info.getValue() as string}</span>
    },
    {
      header: 'DTE',
      accessorKey: 'dte',
      cell: info => {
        const dte = info.getValue() as number;
        return (
          <span className={dte <= 21 ? "text-warning font-bold" : "text-text-primary"}>
             {dte}d
          </span>
        );
      }
    },
    {
      header: 'P&L (Open)',
      accessorKey: 'unrealized_pnl',
      cell: info => {
        const val = info.getValue() as number;
        return (
          <span className={val >= 0 ? "text-profit" : "text-loss"}>
            {formatCurrency(val)}
          </span>
        );
      }
    },
    {
      header: '% to TP',
      accessorKey: 'pct_to_tp',
      cell: info => {
        const val = info.getValue() as number;
        return <span>{val.toFixed(0)}%</span>;
      }
    },
    {
      header: 'Delta',
      accessorKey: 'short_delta',
      cell: info => (info.getValue() as number).toFixed(2)
    },
    {
      header: 'IVR',
      accessorKey: 'ivr',
      cell: info => (info.getValue() as number).toFixed(0)
    },
    {
        header: 'Warnings',
        accessorKey: 'warnings',
        cell: info => {
            const warnings = (info.getValue() as any);
            if (!Array.isArray(warnings) || warnings.length === 0) return null;
            return (
                <div className="flex gap-1">
                    {warnings.map((w: string) => (
                        <StatusChip key={w} status="warning" label={w} icon={AlertCircle} className="bg-yellow-500/20 text-yellow-200 border-yellow-500/30" />
                    ))}
                </div>
            );
        }
    }
  ], []);

  if (loading) return <div className="text-text-secondary animate-pulse">Loading positions...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
         <h2 className="text-xl font-bold text-white">Open Positions</h2>
         <div className="text-sm text-text-secondary">
            {displayPositions.length} active trades
         </div>
      </div>
      
      <DataTable 
        columns={columns} 
        data={displayPositions} 
        onRowClick={(row) => console.log('View trade', row.id)}
      />
    </div>
  );
}
