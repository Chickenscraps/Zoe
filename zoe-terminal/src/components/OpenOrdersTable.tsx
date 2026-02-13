import { useEffect, useMemo, useState } from 'react';
import type { ColumnDef } from '@tanstack/react-table';
import { DataTable } from './DataTable';
import { formatCurrency, formatDate, cn } from '../lib/utils';
import { useDashboardData } from '../hooks/useDashboardData';
import { ClipboardList } from 'lucide-react';

interface OrderRow {
  id: string;
  symbol: string;
  side: 'buy' | 'sell';
  order_type: string;
  notional: number | null;
  qty: number | null;
  limit_price: number | null;
  status: string;
  requested_at: string;
  replace_count: number;
  remaining_qty: number | null;
  next_action_at: string | null;
  intent_group_id: string | null;
  cancel_reason_code: string | null;
}

interface OpenOrdersTableProps {
  hideHeader?: boolean;
  className?: string;
}

const STATUS_COLORS: Record<string, string> = {
  new: 'text-accent',
  submitted: 'text-accent',
  working: 'text-accent',
  partially_filled: 'text-warning',
  cancel_pending: 'text-warning',
  filled: 'text-profit',
  canceled: 'text-text-dim',
  cancelled: 'text-text-dim',
  rejected: 'text-loss',
};

function formatAge(requestedAt: string): string {
  const age = Date.now() - new Date(requestedAt).getTime();
  if (age < 60_000) return `${Math.floor(age / 1000)}s`;
  if (age < 3600_000) return `${Math.floor(age / 60_000)}m`;
  return `${Math.floor(age / 3600_000)}h`;
}

function formatCountdown(nextActionAt: string | null): string | null {
  if (!nextActionAt) return null;
  const remaining = new Date(nextActionAt).getTime() - Date.now();
  if (remaining <= 0) return 'now';
  if (remaining < 60_000) return `${Math.floor(remaining / 1000)}s`;
  return `${Math.floor(remaining / 60_000)}m`;
}

export function OpenOrdersTable({ hideHeader, className }: OpenOrdersTableProps) {
  const { cryptoOrders } = useDashboardData();
  const [, setTick] = useState(0);

  // Force re-render every second for live countdowns
  useEffect(() => {
    const iv = setInterval(() => setTick(t => t + 1), 1000);
    return () => clearInterval(iv);
  }, []);

  const mapOrder = (o: typeof cryptoOrders[number]): OrderRow => ({
    id: o.id,
    symbol: o.symbol,
    side: o.side,
    order_type: o.order_type,
    notional: o.notional,
    qty: o.qty,
    limit_price: o.limit_price ?? null,
    status: o.status,
    requested_at: o.requested_at,
    replace_count: o.replace_count ?? 0,
    remaining_qty: o.remaining_qty ?? null,
    next_action_at: o.next_action_at ?? null,
    intent_group_id: o.intent_group_id ?? null,
    cancel_reason_code: o.cancel_reason_code ?? null,
  });

  // Show only open/pending orders (not yet terminal)
  const openOrders = useMemo<OrderRow[]>(() => {
    if (!cryptoOrders || cryptoOrders.length === 0) return [];
    return cryptoOrders
      .filter(o => ['new', 'submitted', 'working', 'partially_filled', 'cancel_pending'].includes(o.status))
      .map(mapOrder);
  }, [cryptoOrders]);

  // Recent completed orders (last 10) for context
  const recentOrders = useMemo<OrderRow[]>(() => {
    if (!cryptoOrders || cryptoOrders.length === 0) return [];
    return cryptoOrders
      .filter(o => ['filled', 'canceled', 'cancelled', 'rejected'].includes(o.status))
      .slice(0, 10)
      .map(mapOrder);
  }, [cryptoOrders]);

  const allRows = useMemo(() => [...openOrders, ...recentOrders], [openOrders, recentOrders]);

  // Detect stuck orders (age > 5min and replace_count >= 3)
  const stuckOrders = useMemo(() => {
    return openOrders.filter(o => {
      const age = Date.now() - new Date(o.requested_at).getTime();
      return age > 300_000 && o.replace_count >= 3;
    });
  }, [openOrders]);

  const columns = useMemo<ColumnDef<OrderRow>[]>(() => [
    {
      header: 'Symbol',
      accessorKey: 'symbol',
      cell: info => <span className="font-semibold text-white">{(info.getValue() as string).replace('-USD', '')}</span>
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
      header: 'Limit',
      accessorKey: 'limit_price',
      cell: info => {
        const price = info.getValue() as number | null;
        if (!price) return <span className="text-text-dim text-[10px]">MKT</span>;
        return <span className="tabular-nums text-[10px]">${price >= 1 ? price.toFixed(2) : price.toFixed(6)}</span>;
      }
    },
    {
      header: 'Status',
      accessorKey: 'status',
      cell: info => {
        const status = info.getValue() as string;
        const row = info.row.original;
        const display = status.replace(/_/g, ' ');
        const isStuck = openOrders.some(
          o => o.id === row.id && stuckOrders.some(s => s.id === o.id)
        );
        return (
          <span className={cn(
            'font-semibold uppercase text-[10px] tracking-wider',
            isStuck ? 'text-loss animate-pulse' : (STATUS_COLORS[status] || 'text-text-dim')
          )}>
            {['new', 'submitted', 'working'].includes(status) ? '● ' : ''}{display}
            {isStuck && ' ⚠'}
          </span>
        );
      }
    },
    {
      header: 'Age',
      accessorKey: 'requested_at',
      cell: info => {
        const requested = info.getValue() as string;
        const row = info.row.original;
        const isOpen = ['new', 'submitted', 'working', 'partially_filled'].includes(row.status);
        if (!isOpen) {
          return (
            <span className="text-text-dim text-[10px] tabular-nums">
              {formatDate(requested)}
            </span>
          );
        }
        const age = formatAge(requested);
        return (
          <span className="text-text-secondary text-[10px] tabular-nums font-mono">
            {age}
          </span>
        );
      }
    },
    {
      header: 'R#',
      id: 'replace_count',
      accessorFn: row => row.replace_count,
      cell: info => {
        const count = info.getValue() as number;
        if (!count) return <span className="text-text-dim text-[10px]">—</span>;
        return (
          <span className={cn(
            'text-[10px] tabular-nums font-mono',
            count >= 3 ? 'text-loss' : 'text-text-secondary'
          )}>
            {count}
          </span>
        );
      }
    },
    {
      header: 'Next',
      id: 'next_action',
      accessorFn: row => row.next_action_at,
      cell: info => {
        const nextAction = info.getValue() as string | null;
        const row = info.row.original;
        if (!['new', 'submitted', 'working', 'partially_filled'].includes(row.status)) {
          if (row.cancel_reason_code) {
            return <span className="text-text-dim text-[10px]">{row.cancel_reason_code}</span>;
          }
          return <span className="text-text-dim text-[10px]">—</span>;
        }
        const countdown = formatCountdown(nextAction);
        if (!countdown) return <span className="text-text-dim text-[10px]">—</span>;
        return (
          <span className={cn(
            'text-[10px] tabular-nums font-mono',
            countdown === 'now' ? 'text-warning animate-pulse' : 'text-text-secondary'
          )}>
            {countdown}
          </span>
        );
      }
    },
  ], [openOrders, stuckOrders]);

  return (
    <div className={className}>
      {!hideHeader && (
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted flex items-center gap-2">
            <ClipboardList className="w-3 h-3 text-accent" /> Orders
          </h3>
          <span className="text-[9px] font-bold text-text-dim uppercase tracking-widest">
            {stuckOrders.length > 0
              ? `⚠ ${stuckOrders.length} stuck`
              : openOrders.length > 0
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
