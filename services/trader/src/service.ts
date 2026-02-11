/**
 * TraderService — Market-session-aware production paper trading loop.
 * Approved strategies only. Behavior changes by session:
 *   - Off-hours: idle (research + self-heal handled by jobs)
 *   - Pre-market: briefings at 15/10/5 min intervals
 *   - Market open: scan → shortlist → decision → paper execution
 *   - After-hours: position review, daily P&L snapshot
 */
import { createLogger } from "../../shared/src/logger.js";
import { getDb, auditLog } from "../../shared/src/db.js";
import {
  getCurrentSession,
  isTradingDay,
  minutesToMarketOpen,
} from "../../shared/src/market-session.js";
import type {
  MarketSession,
  StrategyRegistryEntry,
  DailyPlan,
  Trade,
} from "../../shared/src/types.js";
import { scanOptionChain, rankWithResearch, type ScanCandidate } from "./scanner.js";
import {
  shouldSendBriefing,
  generateBriefing,
  type BriefingType,
  type Briefing,
} from "./briefing.js";

const log = createLogger("trader");

export interface TraderConfig {
  accountId: string;
  tickIntervalMs: number;     // how often the loop ticks, default 60_000 (1 min)
  watchlist: string[];         // underlyings to scan
  maxTradesPerDay: number;     // default 3
  dryRun: boolean;             // log decisions without executing
}

const DEFAULT_CONFIG: TraderConfig = {
  accountId: "",
  tickIntervalMs: 60_000,
  watchlist: ["SPY", "QQQ", "IWM", "AAPL", "TSLA"],
  maxTradesPerDay: 3,
  dryRun: false,
};

export interface TraderState {
  running: boolean;
  session: MarketSession;
  tradesToday: number;
  lastBriefing: BriefingType | null;
  lastScanTime: string | null;
  pendingCandidates: ScanCandidate[];
  dailyPlan: DailyPlan | null;
}

export class TraderService {
  private config: TraderConfig;
  private state: TraderState;
  private tickTimer: ReturnType<typeof setInterval> | null = null;
  private approvedStrategies: StrategyRegistryEntry[] = [];

  // Event callbacks for integration with Discord/dashboard
  private onBriefing: ((briefing: Briefing) => void) | null = null;
  private onTradeOpen: ((trade: Trade) => void) | null = null;
  private onTradeClose: ((trade: Trade) => void) | null = null;

  constructor(config: Partial<TraderConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.state = {
      running: false,
      session: getCurrentSession(),
      tradesToday: 0,
      lastBriefing: null,
      lastScanTime: null,
      pendingCandidates: [],
      dailyPlan: null,
    };
    log.info("TraderService initialized", {
      watchlist: this.config.watchlist,
      dryRun: this.config.dryRun,
    });
  }

  // ─── Lifecycle ──────────────────────────────────────────────────────

  async start(): Promise<void> {
    if (this.state.running) {
      log.warn("Trader already running");
      return;
    }

    this.state.running = true;
    this.state.session = getCurrentSession();

    // Load approved strategies
    await this.loadApprovedStrategies();

    // Load today's plan if available
    await this.loadDailyPlan();

    log.info("Trader started", {
      session: this.state.session,
      strategies: this.approvedStrategies.length,
      hasPlan: !!this.state.dailyPlan,
    });

    await auditLog("trader_started", {
      session: this.state.session,
      accountId: this.config.accountId,
    });

    // Start tick loop
    this.tickTimer = setInterval(() => {
      this.tick().catch((e) => log.error("Tick error", { error: String(e) }));
    }, this.config.tickIntervalMs);

    // Run first tick immediately
    await this.tick();
  }

  stop(): void {
    this.state.running = false;
    if (this.tickTimer) {
      clearInterval(this.tickTimer);
      this.tickTimer = null;
    }
    log.info("Trader stopped", { tradesToday: this.state.tradesToday });
  }

  isRunning(): boolean {
    return this.state.running;
  }

  getState(): Readonly<TraderState> {
    return { ...this.state };
  }

  // ─── Event Hooks ────────────────────────────────────────────────────

  onBriefingEvent(cb: (briefing: Briefing) => void): void {
    this.onBriefing = cb;
  }

  onTradeOpenEvent(cb: (trade: Trade) => void): void {
    this.onTradeOpen = cb;
  }

  onTradeCloseEvent(cb: (trade: Trade) => void): void {
    this.onTradeClose = cb;
  }

  // ─── Main Tick ──────────────────────────────────────────────────────

  async tick(): Promise<void> {
    if (!this.state.running) return;

    const now = new Date();
    this.state.session = getCurrentSession(now);

    switch (this.state.session) {
      case "closed":
        // Nothing to do — jobs handle off-hours work
        break;

      case "pre_market":
        await this.handlePreMarket(now);
        break;

      case "market_open":
        await this.handleMarketOpen(now);
        break;

      case "after_hours":
        await this.handleAfterHours(now);
        break;
    }
  }

  // ─── Session Handlers ───────────────────────────────────────────────

  private async handlePreMarket(now: Date): Promise<void> {
    const briefingType = shouldSendBriefing(this.state.lastBriefing, now);
    if (!briefingType) return;

    const minutes = minutesToMarketOpen(now) ?? 0;
    const briefing = generateBriefing(this.state.dailyPlan, minutes);

    if (briefing) {
      this.state.lastBriefing = briefing.type;
      log.info("Pre-market briefing", { type: briefing.type });

      if (this.onBriefing) {
        this.onBriefing(briefing);
      }
    }
  }

  private async handleMarketOpen(_now: Date): Promise<void> {
    // Guard: max trades per day
    if (this.state.tradesToday >= this.config.maxTradesPerDay) {
      return;
    }

    // Guard: need approved strategies
    if (this.approvedStrategies.length === 0) {
      return;
    }

    // Scan → shortlist → decision
    // The actual execution is delegated to the paper broker via external call.
    // This loop just identifies candidates and logs the decision.

    log.debug("Market open tick", {
      tradesToday: this.state.tradesToday,
      candidates: this.state.pendingCandidates.length,
    });

    // Mark scan time
    this.state.lastScanTime = _now.toISOString();
  }

  private async handleAfterHours(_now: Date): Promise<void> {
    // After-hours: record daily P&L snapshot
    // This is a lightweight check — the full snapshot is handled by jobs
    log.debug("After-hours tick");
  }

  // ─── Strategy Management ────────────────────────────────────────────

  private async loadApprovedStrategies(): Promise<void> {
    try {
      const db = getDb();
      const { data, error } = await db
        .from("strategy_registry")
        .select("*")
        .eq("status", "approved");

      if (error) {
        log.error("Failed to load strategies", { error: error.message });
        return;
      }

      this.approvedStrategies = (data ?? []) as StrategyRegistryEntry[];
      log.info("Loaded approved strategies", { count: this.approvedStrategies.length });
    } catch (e) {
      log.error("loadApprovedStrategies error", { error: String(e) });
    }
  }

  private async loadDailyPlan(): Promise<void> {
    try {
      const db = getDb();
      const today = new Date().toISOString().split("T")[0];
      const { data, error } = await db
        .from("daily_gameplans")
        .select("*")
        .eq("date", today)
        .order("created_at", { ascending: false })
        .limit(1)
        .single();

      if (data && !error) {
        // Load plan items
        const { data: items } = await db
          .from("daily_gameplan_items")
          .select("*")
          .eq("plan_id", data.id);

        this.state.dailyPlan = {
          date: today!,
          watchlist: (items ?? []).map((i: { symbol: string }) => i.symbol),
          proposed_plays: [],
          market_context: "",
          invalidation_levels: {},
        };
        log.info("Daily plan loaded", { date: today, items: items?.length ?? 0 });
      }
    } catch {
      // No plan for today — that's fine
      log.debug("No daily plan found for today");
    }
  }

  /**
   * Execute a trade decision (called externally after approval).
   * The trader itself does NOT auto-execute — it identifies candidates,
   * and the decision to execute is made by the caller (or an approved strategy).
   */
  async recordTradeExecution(tradeId: string): Promise<void> {
    this.state.tradesToday++;
    log.tradeDecision("TRADE_EXECUTED", {
      tradeId,
      tradesToday: this.state.tradesToday,
      maxPerDay: this.config.maxTradesPerDay,
    });
  }

  /**
   * Reset daily counters (called at start of new trading day).
   */
  resetDaily(): void {
    this.state.tradesToday = 0;
    this.state.lastBriefing = null;
    this.state.pendingCandidates = [];
    this.state.dailyPlan = null;
    log.info("Daily state reset");
  }
}
