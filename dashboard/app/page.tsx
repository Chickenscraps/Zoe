"use client";

import { useEffect, useState, useCallback } from "react";
import { StatusPanel } from "@/components/status-panel";
import { PositionsTable } from "@/components/positions-table";
import { SignalsTable } from "@/components/signals-table";
import { EquityChart } from "@/components/equity-chart";
import { EventsFeed } from "@/components/events-feed";
import { CircuitBreakers } from "@/components/circuit-breakers";
import {
  fetchPositions,
  fetchSignals,
  fetchLatestRegime,
  fetchState,
  fetchCashSnapshots,
  fetchPnlDaily,
  fetchHeartbeats,
  fetchRecentEvents,
} from "@/lib/queries";
import type {
  Position,
  Signal,
  Regime,
  EfState,
  CashSnapshot,
  PnlDaily,
  HealthHeartbeat,
  ZoeEvent,
} from "@/lib/types";
import { RefreshCw } from "lucide-react";

const REFRESH_INTERVAL = 15_000; // 15s auto-refresh

export default function Dashboard() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [regime, setRegime] = useState<Regime | null>(null);
  const [state, setState] = useState<EfState[]>([]);
  const [cashSnapshots, setCashSnapshots] = useState<CashSnapshot[]>([]);
  const [pnlDaily, setPnlDaily] = useState<PnlDaily[]>([]);
  const [heartbeats, setHeartbeats] = useState<HealthHeartbeat[]>([]);
  const [events, setEvents] = useState<ZoeEvent[]>([]);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const [pos, sig, reg, st, cash, pnl, hb, ev] = await Promise.all([
        fetchPositions(),
        fetchSignals(),
        fetchLatestRegime(),
        fetchState(),
        fetchCashSnapshots(),
        fetchPnlDaily(),
        fetchHeartbeats(),
        fetchRecentEvents(),
      ]);
      setPositions(pos);
      setSignals(sig);
      setRegime(reg);
      setState(st);
      setCashSnapshots(cash);
      setPnlDaily(pnl);
      setHeartbeats(hb);
      setEvents(ev);
      setLastRefresh(new Date());
    } catch (err) {
      console.error("Refresh failed:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, REFRESH_INTERVAL);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <h1 className="text-lg font-semibold tracking-tight">
              Edge Factory
            </h1>
            <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs font-medium text-emerald-400">
              LIVE
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground">
              {lastRefresh.toLocaleTimeString()}
            </span>
            <button
              onClick={refresh}
              className="rounded-md p-1.5 text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
              title="Refresh now"
            >
              <RefreshCw
                className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
              />
            </button>
          </div>
        </div>
      </header>

      {/* Main grid */}
      <main className="mx-auto max-w-7xl px-4 py-6">
        {loading && positions.length === 0 ? (
          <div className="flex items-center justify-center py-32">
            <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {/* Row 1: Status (full width on lg) */}
            <StatusPanel
              regime={regime}
              heartbeats={heartbeats}
              state={state}
            />

            {/* Row 2: Equity + Circuit Breakers */}
            <EquityChart
              cashSnapshots={cashSnapshots}
              pnlDaily={pnlDaily}
            />
            <CircuitBreakers state={state} />

            {/* Row 3: Positions (full width) */}
            <PositionsTable positions={positions} />

            {/* Row 4: Signals + Events */}
            <SignalsTable signals={signals} />
            <EventsFeed events={events} />
          </div>
        )}
      </main>
    </div>
  );
}
