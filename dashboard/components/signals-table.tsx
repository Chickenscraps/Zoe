"use client";

import { Card } from "./card";
import { timeAgo } from "@/lib/utils";
import type { Signal } from "@/lib/types";
import { ArrowUpCircle, ArrowDownCircle, MinusCircle } from "lucide-react";

interface SignalsTableProps {
  signals: Signal[];
}

const dirIcon: Record<string, React.ReactNode> = {
  LONG: <ArrowUpCircle className="inline h-4 w-4 text-emerald-400" />,
  SHORT: <ArrowDownCircle className="inline h-4 w-4 text-red-400" />,
  FLAT: <MinusCircle className="inline h-4 w-4 text-muted-foreground" />,
};

export function SignalsTable({ signals }: SignalsTableProps) {
  return (
    <Card title="Recent Signals" className="col-span-full lg:col-span-1">
      {signals.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          No signals yet
        </p>
      ) : (
        <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
          {signals.map((s) => (
            <div
              key={s.id}
              className="flex items-center gap-3 rounded-md bg-secondary/50 px-3 py-2"
            >
              <div className="shrink-0">
                {dirIcon[s.direction] ?? dirIcon.FLAT}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-2">
                  <span className="font-mono font-medium">{s.symbol}</span>
                  <span className="text-xs text-muted-foreground">
                    {s.strategy_name}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span>str: {(s.strength * 100).toFixed(0)}%</span>
                  <span>&middot;</span>
                  <span>{timeAgo(s.generated_at)}</span>
                  {s.acted_on && (
                    <span className="rounded bg-emerald-500/20 px-1 text-emerald-400">
                      acted
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
