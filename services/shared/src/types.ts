/**
 * Zoe V4 — Shared Type Definitions
 * All services import from @zoe/shared/types
 */

// ─── Account & Identity ───────────────────────────────────────────────

export interface User {
  id: string; // UUID
  discord_id: string;
  username: string;
  created_at: string;
  last_seen: string;
}

export interface Account {
  id: string;
  user_id: string;
  instance_id: string;
  equity: number;
  cash: number;
  buying_power: number;
  pdt_count: number;
  day_trades_history: DayTrade[];
  updated_at: string;
}

export interface DayTrade {
  trade_id: string;
  symbol: string;
  open_time: string;
  close_time: string;
  pnl: number;
}

// ─── Trading ──────────────────────────────────────────────────────────

export type OrderSide = "buy" | "sell";
export type OrderType = "market" | "limit" | "stop" | "stop_limit";
export type OrderStatus = "new" | "pending" | "filled" | "partial" | "cancelled" | "rejected";
export type TradeStatus = "open" | "closed" | "expired";
export type PositionDirection = "long" | "short";

export interface Trade {
  id: string;
  account_id: string;
  symbol: string;
  strategy: string;
  strategy_version: string;
  status: TradeStatus;
  entry_time: string;
  exit_time: string | null;
  entry_price: number;
  exit_price: number | null;
  quantity: number;
  pnl: number | null;
  legs: TradeLeg[];
  greeks_at_entry: Greeks | null;
  risk_at_entry: RiskSnapshot | null;
  score_at_entry: Record<string, unknown> | null;
  notes: string | null;
  config_version?: number;
  config_checksum?: string;
}

export interface TradeLeg {
  symbol: string;
  side: OrderSide;
  ratio: number;
  strike?: number;
  expiry?: string;
  contract_type?: "call" | "put";
}

export interface Order {
  id: string;
  trade_id: string | null;
  account_id: string;
  symbol: string;
  side: OrderSide;
  type: OrderType;
  price: number | null;
  quantity: number;
  status: OrderStatus;
  created_at: string;
  filled_at: string | null;
  filled_price: number | null;
  legs: TradeLeg[];
  meta: Record<string, unknown> | null;
  config_version?: number;
  config_checksum?: string;
}

export interface Fill {
  id: string;
  order_id: string;
  trade_id: string | null;
  timestamp: string;
  symbol: string;
  side: OrderSide;
  quantity: number;
  price: number;
  slippage: number;
  fee: number;
}

export interface Position {
  id: string;
  account_id: string;
  symbol: string;
  underlying: string | null;
  quantity: number;
  avg_price: number;
  current_price: number | null;
  market_value: number | null;
  unrealized_pnl: number | null;
  updated_at: string;
}

// ─── Market Data ──────────────────────────────────────────────────────

export interface Quote {
  symbol: string;
  price: number;
  bid: number;
  ask: number;
  timestamp: number;
}

export interface OHLCV {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Greeks {
  delta: number | null;
  gamma: number | null;
  theta: number | null;
  vega: number | null;
  rho?: number | null;
}

export interface OptionContract {
  ticker: string;
  underlying: string;
  expiry: string;
  strike: number;
  contract_type: "call" | "put";
  bid: number;
  ask: number;
  mid: number;
  last: number;
  volume: number;
  open_interest: number;
  implied_volatility: number;
  greeks: Greeks;
}

export interface OptionChainSnapshot {
  id: string;
  underlying: string;
  snapshot_time: string;
  contracts: OptionContract[];
}

// ─── Risk ─────────────────────────────────────────────────────────────

export interface RiskSnapshot {
  max_loss: number;
  max_gain: number | null; // null = unlimited
  risk_reward_ratio: number | null;
  position_size_pct: number;
  account_risk_pct: number;
}

export interface PDTStatus {
  day_trade_count: number;
  max_allowed: number;
  trades_in_window: DayTrade[];
  can_day_trade: boolean;
  next_expiry: string | null; // when oldest trade falls off the 5-day window
}

// ─── Strategy & Experiments ───────────────────────────────────────────

export type StrategyStatus = "candidate" | "approved" | "retired" | "disabled";

export interface StrategyRegistryEntry {
  id: string;
  name: string;
  version: string;
  status: StrategyStatus;
  description: string;
  parameters: Record<string, unknown>;
  gate_criteria: GateCriteria;
  created_at: string;
  updated_at: string;
}

export interface GateCriteria {
  min_trades: number;
  min_win_rate: number;
  max_drawdown: number;
  min_profit_factor: number;
  min_sharpe: number | null;
}

export interface ExperimentRun {
  id: string;
  strategy_id: string;
  strategy_version: string;
  start_date: string;
  end_date: string;
  status: "running" | "completed" | "failed";
  metrics: ExperimentMetrics | null;
  passed_gates: boolean;
  notes: string | null;
  created_at: string;
}

export interface ExperimentMetrics {
  total_trades: number;
  win_rate: number;
  profit_factor: number;
  max_drawdown: number;
  sharpe_ratio: number | null;
  total_pnl: number;
  avg_pnl_per_trade: number;
}

// ─── Research ─────────────────────────────────────────────────────────

export type ResearchSource = "google_trends" | "x_twitter" | "bloomberg" | "news" | "custom";

export interface ResearchItem {
  id: string;
  source: ResearchSource;
  symbol: string | null;
  title: string;
  content: string;
  sentiment_score: number | null;
  relevance_score: number | null;
  fetched_at: string;
  metadata: Record<string, unknown> | null;
}

export interface FeatureDaily {
  id: string;
  symbol: string;
  date: string;
  features: Record<string, number>;
  source_ids: string[];
  created_at: string;
}

// ─── Health & Observability ───────────────────────────────────────────

export type HealthStatus = "healthy" | "degraded" | "unhealthy" | "unknown";

export interface HealthReport {
  id: string;
  timestamp: string;
  overall_status: HealthStatus;
  components: ComponentHealth[];
  tests_passed: number;
  tests_failed: number;
  lint_errors: number;
  typecheck_errors: number;
  simulation_result: string | null;
  notes: string | null;
}

export interface ComponentHealth {
  name: string;
  status: HealthStatus;
  latency_ms: number | null;
  message: string | null;
  last_check: string;
}

// ─── PnL Timeseries ──────────────────────────────────────────────────

export interface PnLPoint {
  timestamp: string;
  equity: number;
  cash: number;
  unrealized_pnl: number;
  realized_pnl: number;
  drawdown: number;
}

// ─── Market Session ───────────────────────────────────────────────────

export type MarketSession =
  | "pre_market"   // 4:00 AM - 9:30 AM ET
  | "market_open"  // 9:30 AM - 4:00 PM ET
  | "after_hours"  // 4:00 PM - 8:00 PM ET
  | "closed";      // 8:00 PM - 4:00 AM ET, weekends, holidays

export interface MarketCalendarDay {
  date: string;
  is_trading_day: boolean;
  market_open: string | null;  // ISO timestamp
  market_close: string | null;
  early_close: boolean;
  session: MarketSession;
}

// ─── Discord ──────────────────────────────────────────────────────────

export interface TradeCard {
  trade: Trade;
  account_summary: { equity: number; pnl_today: number; pnl_total: number };
  screenshot_url: string | null;
}

export interface DailyPlan {
  date: string;
  watchlist: string[];
  proposed_plays: ProposedPlay[];
  market_context: string;
  invalidation_levels: Record<string, number>;
}

export interface ProposedPlay {
  symbol: string;
  strategy: string;
  direction: PositionDirection;
  entry_conditions: string;
  risk: number;
  catalyst: string;
}
