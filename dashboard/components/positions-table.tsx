"use client";

import { Card } from "./card";
import { formatUsd, pnlColor, timeAgo } from "@/lib/utils";
import type { Position } from "@/lib/types";

interface PositionsTableProps {
  positions: Position[];
}

const statusColors: Record<string, string> = {
  pending: "bg-yellow-500/20 text-yellow-400",
  open: "bg-emerald-500/20 text-emerald-400",
  closed_tp: "bg-blue-500/20 text-blue-400",
  closed_sl: "bg-red-500/20 text-red-400",
  closed_timeout: "bg-gray-500/20 text-gray-400",
  closed_regime: "bg-purple-500/20 text-purple-400",
  closed_kill: "bg-red-500/20 text-red-400",
};

export function PositionsTable({ positions }: PositionsTableProps) {
  const open = positions.filter(
    (p) => p.status === "open" || p.status === "pending"
  );
  const closed = positions.filter(
    (p) => p.status !== "open" && p.status !== "pending"
  );

  return (
    <Card
      title="Positions"
      className="col-span-full"
      badge={
        <span className="rounded-full bg-secondary px-2 py-0.5 text-xs text-muted-foreground">
          {open.length} open &middot; {closed.length} closed
        </span>
      }
    >
      {positions.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          No positions yet
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="pb-2 pr-4">Symbol</th>
                <th className="pb-2 pr-4">Side</th>
                <th className="pb-2 pr-4">Entry</th>
                <th className="pb-2 pr-4">Size</th>
                <th className="pb-2 pr-4">TP</th>
                <th className="pb-2 pr-4">SL</th>
                <th className="pb-2 pr-4">P&L</th>
                <th className="pb-2 pr-4">Status</th>
                <th className="pb-2">Age</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => (
                <tr
                  key={p.id}
                  className="border-b border-border/50 last:border-0"
                >
                  <td className="py-2 pr-4 font-mono font-medium">
                    {p.symbol}
                  </td>
                  <td className="py-2 pr-4">
                    <span
                      className={
                        p.side === "buy"
                          ? "text-emerald-400"
                          : "text-red-400"
                      }
                    >
                      {p.side.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-2 pr-4 font-mono">
                    {p.entry_price
                      ? formatUsd(p.entry_price)
                      : "---"}
                  </td>
                  <td className="py-2 pr-4 font-mono">
                    {p.size_usd ? formatUsd(p.size_usd) : "---"}
                  </td>
                  <td className="py-2 pr-4 font-mono text-xs text-muted-foreground">
                    {p.tp_price ? formatUsd(p.tp_price) : "---"}
                  </td>
                  <td className="py-2 pr-4 font-mono text-xs text-muted-foreground">
                    {p.sl_price ? formatUsd(p.sl_price) : "---"}
                  </td>
                  <td className={`py-2 pr-4 font-mono ${pnlColor(p.pnl_usd)}`}>
                    {p.pnl_usd != null ? formatUsd(p.pnl_usd) : "---"}
                  </td>
                  <td className="py-2 pr-4">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs ${
                        statusColors[p.status] ??
                        "bg-secondary text-muted-foreground"
                      }`}
                    >
                      {p.status}
                    </span>
                  </td>
                  <td className="py-2 text-xs text-muted-foreground">
                    {timeAgo(p.entry_time ?? p.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
