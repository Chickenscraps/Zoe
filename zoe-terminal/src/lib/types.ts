export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export interface Database {
  public: {
    Tables: {
      positions: {
        Row: {
          id: string
          instance_id: string
          symbol: string
          strategy: string
          opened_at: string
          dte: number
          short_delta: number
          ivr: number
          credit_debit: 'credit' | 'debit'
          max_risk: number
          unrealized_pnl: number
          pct_to_tp: number
          warnings: Json // string[]
          status: string
          entry_price: number
          current_mark: number
          qty: number
        }
      }
      trades: {
        Row: {
          trade_id: string
          instance_id: string
          symbol: string
          strategy: string
          opened_at: string
          closed_at: string | null
          realized_pnl: number
          r_multiple: number | null
          outcome: 'win' | 'loss' | 'scratch' | 'open'
          rationale: string | null
        }
      }
      pnl_daily: {
        Row: {
          date: string
          instance_id: string
          daily_pnl: number
          equity: number
          drawdown: number
          win_rate: number | null
          expectancy: number | null
          cash_buffer_pct: number
          day_trades_used: number
          realized_pnl: number
          unrealized_pnl: number
        }
      }
      candidate_scans: {
        Row: {
          id: string
          instance_id: string
          symbol: string
          score: number
          score_breakdown: Json // { [key: string]: number }
          info: Json // { ivr: number, liquidity: string, etc }
          recommended_strategy: string
          created_at: string
        }
      }
      thoughts: {
        Row: {
          id: string
          instance_id: string
          content: string
          type: 'scan' | 'entry' | 'exit' | 'health' | 'general'
          symbol: string | null
          created_at: string
          metadata: Json
        }
      }
      health_heartbeat: {
        Row: {
          id: string
          instance_id: string
          component: string
          status: 'ok' | 'warning' | 'error' | 'down'
          last_heartbeat: string
          details: Json
        }
      }
      daily_gameplans: {
        Row: {
            id: string;
            instance_id: string;
            date: string;
            status: 'draft' | 'refined' | 'locked';
            created_at: string;
        }
      }
      daily_gameplan_items: {
          Row: {
              id: string;
              plan_id: string;
              symbol: string;
              catalyst_summary: string | null;
              regime: string | null;
              ivr_tech_snapshot: string | null;
              preferred_strategy: string | null;
              risk_tier: string | null;
              do_not_trade: boolean;
              visual_notes: string | null;
          }
      }
      config: {
        Row: {
          key: string;
          instance_id: string;
          value: Json;
        }
      }
      audit_log: {
          Row: {
              id: string;
              instance_id: string;
              event_type: string;
              message: string;
              created_at: string;
              metadata: Json;
          }
      }
      risk_events: {
          Row: {
              id: string;
              instance_id: string;
              event_type: string;
              severity: 'info' | 'warning' | 'critical';
              message: string;
              created_at: string;
          }
      }
    }
  }
}
