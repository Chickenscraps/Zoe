"use client";

import { Card } from "./card";
import { timeAgo } from "@/lib/utils";
import type { ZoeEvent } from "@/lib/types";
import {
  AlertTriangle,
  Info,
  Zap,
  TrendingUp,
  ShieldAlert,
} from "lucide-react";

interface EventsFeedProps {
  events: ZoeEvent[];
}

const severityIcon: Record<string, React.ReactNode> = {
  critical: <ShieldAlert className="h-3.5 w-3.5 text-red-400" />,
  warning: <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />,
  info: <Info className="h-3.5 w-3.5 text-blue-400" />,
  debug: <Zap className="h-3.5 w-3.5 text-muted-foreground" />,
};

const typeColors: Record<string, string> = {
  SIGNAL: "text-purple-400",
  FILL: "text-emerald-400",
  ORDER: "text-blue-400",
  RISK: "text-amber-400",
  SYSTEM: "text-muted-foreground",
};

export function EventsFeed({ events }: EventsFeedProps) {
  return (
    <Card title="Event Log" className="col-span-full lg:col-span-1">
      {events.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          No events yet
        </p>
      ) : (
        <div className="max-h-80 space-y-1.5 overflow-y-auto pr-1">
          {events.map((e) => (
            <div
              key={e.id}
              className="flex items-start gap-2 rounded-md bg-secondary/30 px-2.5 py-1.5 text-xs"
            >
              <div className="mt-0.5 shrink-0">
                {severityIcon[e.severity] ?? severityIcon.info}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span
                    className={`font-medium ${
                      typeColors[e.type] ?? "text-foreground"
                    }`}
                  >
                    {e.type}
                  </span>
                  <span className="text-muted-foreground">{e.subtype}</span>
                  {e.symbol && (
                    <span className="font-mono text-foreground">
                      {e.symbol}
                    </span>
                  )}
                </div>
                <p className="text-muted-foreground">{timeAgo(e.ts)}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
