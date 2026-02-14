"use client";

import { Card } from "./card";
import { timeAgo } from "@/lib/utils";
import type { Regime, HealthHeartbeat, EfState } from "@/lib/types";
import {
  Activity,
  Shield,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  XCircle,
} from "lucide-react";

interface StatusPanelProps {
  regime: Regime | null;
  heartbeats: HealthHeartbeat[];
  state: EfState[];
}

const regimeColors: Record<string, string> = {
  TRENDING: "text-emerald-400",
  MEAN_REVERTING: "text-blue-400",
  VOLATILE: "text-amber-400",
  TRANSITION: "text-purple-400",
  UNKNOWN: "text-muted-foreground",
};

export function StatusPanel({ regime, heartbeats, state }: StatusPanelProps) {
  const killSwitch = state.find((s) => s.key === "kill_switch");
  const isKilled = killSwitch?.value && (killSwitch.value as Record<string, unknown>).active === true;

  const efHeartbeat = heartbeats.find((h) => h.component === "edge_factory");
  const rhHeartbeat = heartbeats.find((h) => h.component === "robinhood_api");

  return (
    <Card title="System Status" className="col-span-full lg:col-span-2">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {/* Mode */}
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Activity className="h-3.5 w-3.5" />
            Mode
          </div>
          <p className="text-lg font-semibold text-emerald-400">LIVE</p>
        </div>

        {/* Regime */}
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <TrendingUp className="h-3.5 w-3.5" />
            Regime
          </div>
          <p
            className={`text-lg font-semibold ${
              regimeColors[regime?.regime ?? "UNKNOWN"] ?? "text-muted-foreground"
            }`}
          >
            {regime?.regime ?? "---"}
          </p>
          {regime && (
            <p className="text-xs text-muted-foreground">
              {(regime.confidence * 100).toFixed(0)}% conf &middot;{" "}
              {timeAgo(regime.detected_at)}
            </p>
          )}
        </div>

        {/* Kill Switch */}
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Shield className="h-3.5 w-3.5" />
            Kill Switch
          </div>
          {isKilled ? (
            <p className="flex items-center gap-1 text-lg font-semibold text-red-400">
              <XCircle className="h-5 w-5" /> ACTIVE
            </p>
          ) : (
            <p className="flex items-center gap-1 text-lg font-semibold text-emerald-400">
              <CheckCircle className="h-5 w-5" /> Safe
            </p>
          )}
        </div>

        {/* Heartbeats */}
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <AlertTriangle className="h-3.5 w-3.5" />
            Health
          </div>
          <div className="space-y-0.5">
            <HeartbeatRow label="EF" hb={efHeartbeat} />
            <HeartbeatRow label="RH" hb={rhHeartbeat} />
          </div>
        </div>
      </div>
    </Card>
  );
}

function HeartbeatRow({
  label,
  hb,
}: {
  label: string;
  hb: HealthHeartbeat | undefined;
}) {
  if (!hb)
    return (
      <p className="text-sm text-muted-foreground">
        {label}: <span className="text-yellow-400">no data</span>
      </p>
    );
  const ok = hb.status === "ok" || hb.status === "healthy";
  return (
    <p className="text-sm">
      {label}:{" "}
      <span className={ok ? "text-emerald-400" : "text-red-400"}>
        {hb.status}
      </span>{" "}
      <span className="text-xs text-muted-foreground">
        {timeAgo(hb.last_heartbeat)}
      </span>
    </p>
  );
}
