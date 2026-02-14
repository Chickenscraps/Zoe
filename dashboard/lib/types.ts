export interface Position {
  id: string;
  symbol: string;
  side: string;
  entry_price: number | null;
  entry_time: string | null;
  size_usd: number | null;
  tp_price: number | null;
  sl_price: number | null;
  status: string;
  exit_price: number | null;
  exit_time: string | null;
  pnl_usd: number | null;
  signal_id: string | null;
  order_id: string | null;
  created_at: string;
}

export interface Signal {
  id: string;
  symbol: string;
  direction: string;
  strength: number;
  regime_id: string | null;
  features: Record<string, unknown>;
  generated_at: string;
  strategy_name: string;
  acted_on: boolean;
  mode: string | null;
}

export interface Regime {
  id: string;
  regime: string;
  confidence: number;
  detected_at: string;
  features_used: Record<string, unknown>;
}

export interface EfState {
  key: string;
  value: Record<string, unknown>;
  updated_at: string;
}

export interface CashSnapshot {
  id?: string;
  cash_available: number;
  buying_power: number;
  mode: string;
  taken_at: string;
}

export interface PnlDaily {
  date: string;
  instance_id: string;
  equity: number;
  daily_pnl: number;
  drawdown: number;
  cash_buffer_pct: number;
  day_trades_used: number;
  realized_pnl: number;
  unrealized_pnl: number;
  mode: string;
}

export interface HealthHeartbeat {
  instance_id: string;
  component: string;
  status: string;
  last_heartbeat: string;
  details: Record<string, unknown>;
  mode: string;
}

export interface ZoeEvent {
  id: string;
  ts: string;
  mode: string;
  source: string;
  type: string;
  subtype: string;
  symbol: string | null;
  severity: string;
  body: Record<string, unknown>;
  meta: Record<string, unknown>;
  created_at: string;
}
