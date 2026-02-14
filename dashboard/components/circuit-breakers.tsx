"use client";

import { Card } from "./card";
import { timeAgo } from "@/lib/utils";
import type { EfState } from "@/lib/types";
import { Shield, ShieldAlert } from "lucide-react";

interface CircuitBreakersProps {
  state: EfState[];
}

const knownKeys: Record<string, { label: string; dangerWhen: string }> = {
  kill_switch: { label: "Kill Switch", dangerWhen: "active" },
  dd_soft: { label: "DD Soft (5%)", dangerWhen: "tripped" },
  dd_hard: { label: "DD Hard (20%)", dangerWhen: "tripped" },
  consecutive_loss: { label: "Consec. Loss", dangerWhen: "tripped" },
  spread_blowout: { label: "Spread Blowout", dangerWhen: "tripped" },
};

export function CircuitBreakers({ state }: CircuitBreakersProps) {
  // Show relevant circuit breaker keys
  const breakers = state.filter(
    (s) =>
      s.key.includes("kill") ||
      s.key.includes("dd") ||
      s.key.includes("loss") ||
      s.key.includes("spread") ||
      s.key.includes("breaker") ||
      s.key.includes("circuit")
  );

  // Also show any other state as raw KV
  const other = state.filter(
    (s) =>
      !s.key.includes("kill") &&
      !s.key.includes("dd") &&
      !s.key.includes("loss") &&
      !s.key.includes("spread") &&
      !s.key.includes("breaker") &&
      !s.key.includes("circuit")
  );

  return (
    <Card title="Circuit Breakers" className="col-span-full lg:col-span-1">
      {state.length === 0 ? (
        <div className="flex items-center gap-2 py-4">
          <Shield className="h-5 w-5 text-emerald-400" />
          <span className="text-sm text-muted-foreground">
            All clear &mdash; no breakers in state
          </span>
        </div>
      ) : (
        <div className="space-y-2">
          {breakers.map((s) => {
            const meta = knownKeys[s.key];
            const val = s.value as Record<string, unknown>;
            const isActive =
              val.active === true ||
              val.tripped === true ||
              val.status === "tripped";

            return (
              <div
                key={s.key}
                className={`flex items-center justify-between rounded-md px-3 py-2 ${
                  isActive
                    ? "bg-red-500/10 border border-red-500/30"
                    : "bg-secondary/50"
                }`}
              >
                <div className="flex items-center gap-2">
                  {isActive ? (
                    <ShieldAlert className="h-4 w-4 text-red-400" />
                  ) : (
                    <Shield className="h-4 w-4 text-emerald-400" />
                  )}
                  <span className="text-sm font-medium">
                    {meta?.label ?? s.key}
                  </span>
                </div>
                <div className="text-right text-xs text-muted-foreground">
                  {isActive ? (
                    <span className="text-red-400 font-medium">ACTIVE</span>
                  ) : (
                    <span className="text-emerald-400">OK</span>
                  )}
                  <p>{timeAgo(s.updated_at)}</p>
                </div>
              </div>
            );
          })}

          {other.length > 0 && (
            <div className="mt-2 space-y-1 border-t border-border pt-2">
              <p className="text-xs text-muted-foreground mb-1">State KV</p>
              {other.map((s) => (
                <div
                  key={s.key}
                  className="flex justify-between text-xs bg-secondary/30 rounded px-2 py-1"
                >
                  <span className="font-mono text-muted-foreground">
                    {s.key}
                  </span>
                  <span className="font-mono text-foreground truncate max-w-[200px]">
                    {JSON.stringify(s.value)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
