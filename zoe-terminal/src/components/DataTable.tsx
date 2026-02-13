import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  getSortedRowModel,
  type SortingState,
  type ColumnDef,
} from '@tanstack/react-table';
import { useState } from 'react';
import { cn } from '../lib/utils';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface DataTableProps<TData> {
  columns: ColumnDef<TData, any>[];
  data: TData[];
  onRowClick?: (row: TData) => void;
  className?: string;
  emptyMessage?: string;
}

export function DataTable<TData>({ columns, data, onRowClick, className, emptyMessage = "No data available" }: DataTableProps<TData>) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
    },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className={cn("card-premium overflow-hidden", className)}>
      {/* Desktop: standard table */}
      <div className="hidden md:block overflow-x-auto scrollbar-thin scrollbar-thumb-border-strong scrollbar-track-transparent">
        <table className="w-full text-sm text-left border-collapse">
          <thead className="bg-surface-highlight/50 text-text-muted uppercase text-[10px] font-semibold tracking-[0.15em] border-b border-border sticky top-0 z-10">
            {table.getHeaderGroups().map(headerGroup => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map(header => (
                  <th
                    key={header.id}
                    className="px-4 lg:px-6 py-3 lg:py-4 cursor-pointer select-none hover:text-white transition-colors"
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    <div className="flex items-center gap-2">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {{
                        asc: <ChevronUp className="w-3.5 h-3.5 text-profit" />,
                        desc: <ChevronDown className="w-3.5 h-3.5 text-loss" />,
                      }[header.column.getIsSorted() as string] ?? null}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-border/50">
            {table.getRowModel().rows.length > 0 ? (
              table.getRowModel().rows.map(row => (
                <tr
                  key={row.id}
                  className={cn(
                    "hover:bg-white/[0.02] transition-colors group",
                    onRowClick && "cursor-pointer"
                  )}
                  onClick={() => onRowClick?.(row.original)}
                >
                  {row.getVisibleCells().map(cell => (
                    <td key={cell.id} className="px-4 lg:px-6 py-3 lg:py-4 whitespace-nowrap text-text-primary tabular-nums font-medium">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={columns.length} className="px-6 py-12 text-center text-text-dim italic font-medium">
                  {emptyMessage}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Mobile: card layout — stacked key-value pairs */}
      <div className="md:hidden">
        {table.getRowModel().rows.length > 0 ? (
          <div className="divide-y divide-border/50">
            {table.getRowModel().rows.map(row => (
              <div
                key={row.id}
                className={cn(
                  "p-4 transition-colors active:bg-white/[0.03]",
                  onRowClick && "cursor-pointer"
                )}
                onClick={() => onRowClick?.(row.original)}
              >
                {/* First column rendered as card header */}
                {row.getVisibleCells().length > 0 && (
                  <div className="text-base font-bold text-white mb-2">
                    {flexRender(row.getVisibleCells()[0].column.columnDef.cell, row.getVisibleCells()[0].getContext())}
                  </div>
                )}
                {/* Remaining columns as 2-col key-value grid */}
                <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                  {row.getVisibleCells().slice(1).map(cell => {
                    const header = cell.column.columnDef.header;
                    const headerText = typeof header === 'string' ? header : cell.column.id;
                    return (
                      <div key={cell.id} className="flex flex-col">
                        <span className="text-[10px] text-text-muted uppercase tracking-wider font-medium">{headerText}</span>
                        <span className="text-xs text-text-primary tabular-nums font-medium mt-0.5">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="px-6 py-12 text-center text-text-dim italic font-medium">
            {emptyMessage}
          </div>
        )}
      </div>
    </div>
  );
}
