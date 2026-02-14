"use client";

import { Card } from "./card";
import { formatUsd } from "@/lib/utils";
import type { CashSnapshot, PnlDaily } from "@/lib/types";

interface EquityChartProps {
  cashSnapshots: CashSnapshot[];
  pnlDaily: PnlDaily[];
}

export function EquityChart({ cashSnapshots, pnlDaily }: EquityChartProps) {
  // Prefer pnl_daily for equity curve, fall back to cash snapshots
  const points =
    pnlDaily.length > 0
      ? pnlDaily
          .slice()
          .reverse()
          .map((d) => ({
            label: d.date,
            value: d.equity,
            pnl: d.daily_pnl,
            dd: d.drawdown,
          }))
      : cashSnapshots
          .slice()
          .reverse()
          .map((s) => ({
            label: new Date(s.taken_at).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            }),
            value: s.buying_power,
            pnl: 0,
            dd: 0,
          }));

  if (points.length === 0) {
    return (
      <Card title="Equity" className="col-span-full lg:col-span-1">
        <p className="py-8 text-center text-sm text-muted-foreground">
          No equity data yet
        </p>
      </Card>
    );
  }

  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const currentEquity = values[values.length - 1];
  const startEquity = values[0];
  const totalChange = currentEquity - startEquity;

  // Simple SVG sparkline
  const svgW = 400;
  const svgH = 80;
  const pathD = points
    .map((p, i) => {
      const x = (i / Math.max(points.length - 1, 1)) * svgW;
      const y = svgH - ((p.value - min) / range) * (svgH - 8) - 4;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <Card title="Equity" className="col-span-full lg:col-span-1">
      <div className="mb-2 flex items-baseline gap-3">
        <span className="text-2xl font-bold font-mono">
          {formatUsd(currentEquity)}
        </span>
        <span
          className={`text-sm font-mono ${
            totalChange >= 0 ? "text-emerald-400" : "text-red-400"
          }`}
        >
          {totalChange >= 0 ? "+" : ""}
          {formatUsd(totalChange)}
        </span>
      </div>

      <svg
        viewBox={`0 0 ${svgW} ${svgH}`}
        className="w-full"
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
            <stop
              offset="0%"
              stopColor={totalChange >= 0 ? "#34d399" : "#f87171"}
              stopOpacity="0.3"
            />
            <stop
              offset="100%"
              stopColor={totalChange >= 0 ? "#34d399" : "#f87171"}
              stopOpacity="0"
            />
          </linearGradient>
        </defs>
        {/* Area fill */}
        <path
          d={`${pathD} L${svgW},${svgH} L0,${svgH} Z`}
          fill="url(#eqGrad)"
        />
        {/* Line */}
        <path
          d={pathD}
          fill="none"
          stroke={totalChange >= 0 ? "#34d399" : "#f87171"}
          strokeWidth="2"
        />
      </svg>

      {pnlDaily.length > 0 && (
        <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
          <div>
            <span className="text-muted-foreground">Today P&L</span>
            <p
              className={`font-mono ${
                pnlDaily[0].daily_pnl >= 0
                  ? "text-emerald-400"
                  : "text-red-400"
              }`}
            >
              {formatUsd(pnlDaily[0].daily_pnl)}
            </p>
          </div>
          <div>
            <span className="text-muted-foreground">Drawdown</span>
            <p className="font-mono text-amber-400">
              {(pnlDaily[0].drawdown * 100).toFixed(1)}%
            </p>
          </div>
          <div>
            <span className="text-muted-foreground">Realized</span>
            <p
              className={`font-mono ${
                pnlDaily[0].realized_pnl >= 0
                  ? "text-emerald-400"
                  : "text-red-400"
              }`}
            >
              {formatUsd(pnlDaily[0].realized_pnl)}
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}
