import { useMemo } from 'react';
import type { ColumnDef } from '@tanstack/react-table';
import { DataTable } from './DataTable';
import { formatCurrency, formatDate, cn } from '../lib/utils';
import { useDashboardData } from '../hooks/useDashboardData';
import { ClipboardList } from 'lucide-react';

interface OrderRow {
  symbol: string;
  side: 'buy' | 'sell';
  order_type: string;
  notional: number | null;
  qty: number | null;
  status: string;
  requested_at: string;
}

interface OpenOrdersTableProps {
  hideHeader?: boolean;
  className?: string;
}

const STATUS_COLORS: Record<string, string> = {
  new: 'text-accent',
  submitted: 'text-accent',
  partially_filled: 'text-warning',
  filled: 'text-profit',
  canceled: 'text-text-dim',
  rejected: 'text-loss',
};

export function OpenOrdersTable({ hideHeader, className }: OpenOrdersTableProps) {
  const { cryptoOrders } = useDashboardData();

  // Show only open/pending orders (not yet terminal)
  const openOrders = useMemo<OrderRow[]>(() => {
    if (!cryptoOrders || cryptoOrders.length === 0) return [];

    return cryptoOrders
      .filter(o => ['new', 'submitted', 'partially_filled'].includes(o.status))
      .map(o => ({
        symbol: o.symbol,
        side: o.side,
        order_type: o.order_type,
        notional: o.notional,
        qty: o.qty,
        status: o.status,
        requested_at: o.requested_at,
      }));
  }, [cryptoOrders]);

  // Recent completed orders (last 10) for context
  const recentOrders = useMemo<OrderRow[]>(() => {
    if (!cryptoOrders || cryptoOrders.length === 0) return [];

    return cryptoOrders
      .filter(o => ['filled', 'canceled', 'rejected'].includes(o.status))
      .slice(0, 10)
      .map(o => ({
        symbol: o.symbol,
        side: o.side,
        order_type: o.order_type,
        notional: o.notional,
        qty: o.qty,
        status: o.status,
        requested_at: o.requested_at,
      }));
  }, [cryptoOrders]);

  const allRows = useMemo(() => [...openOrders, ...recentOrders], [openOrders, recentOrders]);

  const columns = useMemo<ColumnDef<OrderRow>[]>(() => [
    {
      header: 'Symbol',
      accessorKey: 'symbol',
      cell: info => <span className="font-semibold text-white">{info.getValue() as string}</span>
    },
    {
      header: 'Side',
      accessorKey: 'side',
      cell: info => {
        const side = info.getValue() as string;
        return (
          <span className={cn(
            'font-bold uppercase text-[10px] tracking-wider px-1.5 py-0.5 rounded',
            side === 'buy' ? 'text-profit bg-profit/10' : 'text-loss bg-loss/10'
          )}>
            {side}
          </span>
        );
      }
    },
    {
      header: 'Type',
      accessorKey: 'order_type',
      cell: info => (
        <span className="text-text-secondary uppercase text-[10px] tracking-wider">
          {info.getValue() as string}
        </span>
      )
    },
    {
      header: 'Amount',
      accessorKey: 'notional',
      cell: info => {
        const notional = info.getValue() as number | null;
        const row = info.row.original;
        if (notional) return <span className="tabular-nums">{formatCurrency(notional)}</span>;
        if (row.qty) return <span className="tabular-nums text-text-secondary">{row.qty.toFixed(6)} qty</span>;
        return <span className="text-text-dim">—</span>;
      }
    },
    {
      header: 'Status',
      accessorKey: 'status',
      cell: info => {
        const status = info.getValue() as string;
        const display = status.replace(/_/g, ' ');
        return (
          <span className={cn(
            'font-semibold uppercase text-[10px] tracking-wider',
            STATUS_COLORS[status] || 'text-text-dim'
          )}>
            {status === 'new' || status === 'submitted' ? '● ' : ''}{display}
          </span>
        );
      }
    },
    {
      header: 'Time',
      accessorKey: 'requested_at',
      cell: info => (
        <span className="text-text-dim text-[10px] tabular-nums">
          {formatDate(info.getValue() as string)}
        </span>
      )
    },
  ], []);

  return (
    <div className={className}>
      {!hideHeader && (
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted flex items-center gap-2">
            <ClipboardList className="w-3 h-3 text-accent" /> Orders
          </h3>
          <span className="text-[9px] font-bold text-text-dim uppercase tracking-widest">
            {openOrders.length > 0
              ? `${openOrders.length} open`
              : `${recentOrders.length} recent`
            }
          </span>
        </div>
      )}

      {allRows.length > 0 ? (
        <DataTable
          columns={columns}
          data={allRows}
          emptyMessage="No orders"
        />
      ) : (
        <div className="card-premium p-8 text-center">
          <p className="text-text-dim text-xs">No orders yet</p>
          <p className="text-text-dim/60 text-[9px] mt-1">Orders will appear when the bot submits trades</p>
        </div>
      )}
    </div>
  );
}
