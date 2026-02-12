export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];

export interface Database {
  public: {
    Tables: {
      positions: {
        Row: {
          id: string;
          account_id: string;
          symbol: string;
          underlying: string | null;
          quantity: number;
          avg_price: number;
          current_price: number;
          market_value: number;
          updated_at: string;
        };
      };
      trades: {
        Row: {
          trade_id: string;
          instance_id: string;
          symbol: string;
          strategy: string;
          opened_at: string;
          closed_at: string | null;
          realized_pnl: number;
          r_multiple: number | null;
          outcome: "win" | "loss" | "scratch" | "open";
          rationale: string | null;
        };
      };
      pnl_daily: {
        Row: {
          date: string;
          instance_id: string;
          daily_pnl: number;
          equity: number;
          drawdown: number;
          win_rate: number | null;
          expectancy: number | null;
          cash_buffer_pct: number;
          day_trades_used: number;
          realized_pnl: number;
          unrealized_pnl: number;
          mode: "paper" | "live";
        };
      };
      candidate_scans: {
        Row: {
          id: string;
          instance_id: string;
          symbol: string;
          score: number;
          score_breakdown: Json;
          info: Json;
          recommended_strategy: string;
          created_at: string;
          mode: "paper" | "live";
        };
      };
      thoughts: {
        Row: {
          id: string;
          instance_id: string;
          content: string;
          type: "scan" | "entry" | "exit" | "health" | "general";
          symbol: string | null;
          created_at: string;
          metadata: Json;
          mode: "paper" | "live";
        };
      };
      health_heartbeat: {
        Row: {
          id: string;
          instance_id: string;
          component: string;
          status: "ok" | "warning" | "error" | "down";
          last_heartbeat: string;
          details: Json;
          mode: "paper" | "live";
        };
      };
      daily_gameplans: {
        Row: {
          id: string;
          instance_id: string;
          date: string;
          status: "draft" | "refined" | "locked";
          created_at: string;
        };
      };
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
        };
      };
      config: {
        Row: {
          key: string;
          instance_id: string;
          value: Json;
        };
      };
      audit_log: {
        Row: {
          id: string;
          instance_id: string;
          event_type: string;
          message: string;
          created_at: string;
          metadata: Json;
        };
      };
      risk_events: {
        Row: {
          id: string;
          instance_id: string;
          event_type: string;
          severity: "info" | "warning" | "critical";
          message: string;
          created_at: string;
        };
      };
      crypto_orders: {
        Row: {
          id: string;
          client_order_id: string;
          symbol: string;
          side: "buy" | "sell";
          order_type: "market" | "limit";
          qty: number | null;
          notional: number | null;
          status: "new" | "submitted" | "partially_filled" | "filled" | "canceled" | "rejected";
          requested_at: string;
          submitted_at: string | null;
          updated_at: string;
          raw_response: Json;
          mode: "paper" | "live";
        };
      };
      crypto_tickers: {
        Row: {
          symbol: string;
          price: number;
          change_24h: number | null;
          last_updated: string;
        };
      };
      crypto_fills: {
        Row: {
          id: string;
          order_id: string;
          fill_id: string;
          symbol: string;
          side: "buy" | "sell";
          qty: number;
          price: number;
          fee: number;
          executed_at: string;
          raw_fill: Json;
          mode: "paper" | "live";
        };
      };
      crypto_holdings_snapshots: {
        Row: {
          id: string;
          taken_at: string;
          holdings: Json;
          total_crypto_value: number;
          source: "robinhood";
          mode: "paper" | "live";
        };
      };
      crypto_cash_snapshots: {
        Row: {
          id: string;
          taken_at: string;
          cash_available: number;
          buying_power: number;
          source: "robinhood";
          mode: "paper" | "live";
        };
      };
      crypto_reconciliation_events: {
        Row: {
          id: string;
          taken_at: string;
          local_cash: number;
          rh_cash: number;
          cash_diff: number;
          local_holdings: Json;
          rh_holdings: Json;
          holdings_diff: Json;
          status: "ok" | "degraded";
          reason: string | null;
          mode: "paper" | "live";
        };
      };
      daily_notional: {
        Row: {
          day: string;
          amount: number;
          mode: "paper" | "live";
        };
      };
      agent_state: {
        Row: {
          id: string;
          mode: "paper" | "live";
          instance_id: string;
          state: Json;
          updated_at: string;
        };
      };
      boot_audit: {
        Row: {
          id: string;
          run_id: string;
          mode: "paper" | "live";
          instance_id: string;
          started_at: string;
          finished_at: string | null;
          duration_ms: number | null;
          status: "running" | "ok" | "safe_mode" | "halted" | "error";
          diffs: Json;
          integrity_checks: Json;
          resume_policy: string | null;
          error_message: string | null;
          created_at: string;
        };
      };
      ef_features: {
        Row: {
          id: string;
          symbol: string;
          feature_name: string;
          value: number;
          computed_at: string;
          source: string;
          metadata: Json;
        };
      };
      ef_regimes: {
        Row: {
          id: string;
          regime: string;
          confidence: number;
          detected_at: string;
          features_used: Json;
        };
      };
      ef_signals: {
        Row: {
          id: string;
          symbol: string;
          direction: string;
          strength: number;
          regime_id: string | null;
          features: Json;
          generated_at: string;
          strategy_name: string;
          acted_on: boolean;
        };
      };
      ef_positions: {
        Row: {
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
        };
      };
      ef_state: {
        Row: {
          key: string;
          value: Json;
          updated_at: string;
        };
      };
      market_pivots: {
        Row: {
          id: number;
          symbol: string;
          timeframe: string;
          timestamp: string;
          price: number;
          type: "high" | "low";
          source: "wick" | "body";
          atr_snapshot: number | null;
          confirmed: boolean;
          created_at: string;
        };
      };
      technical_trendlines: {
        Row: {
          id: number;
          symbol: string;
          timeframe: string;
          side: "support" | "resistance";
          slope: number;
          intercept: number;
          start_at: string;
          end_at: string;
          inlier_count: number;
          score: number;
          metadata: Json;
          is_active: boolean;
          created_at: string;
          updated_at: string;
        };
      };
      technical_levels: {
        Row: {
          id: number;
          symbol: string;
          timeframe: string;
          price_centroid: number;
          price_top: number;
          price_bottom: number;
          role: "support" | "resistance" | "flip" | null;
          touch_count: number;
          score: number;
          first_tested: string | null;
          last_tested: string | null;
          is_active: boolean;
          metadata: Json;
          created_at: string;
          updated_at: string;
        };
      };
      structure_events: {
        Row: {
          id: number;
          symbol: string;
          timeframe: string;
          event_type: "breakout" | "breakdown" | "retest";
          reference_id: number | null;
          reference_kind: "trendline" | "level" | null;
          price_at: number;
          confirmed: boolean;
          confirm_count: number;
          reason_json: Json;
          ts: string;
        };
      };
      bounce_events: {
        Row: {
          id: string;
          ts: string;
          symbol: string;
          prev_state: string | null;
          state: string;
          score: number | null;
          reason_json: Json;
        };
      };
      bounce_intents: {
        Row: {
          id: string;
          ts: string;
          symbol: string;
          entry_style: "retest" | "breakout" | null;
          entry_price: number | null;
          expected_move_pct: number | null;
          tp_price: number | null;
          sl_price: number | null;
          score: number | null;
          components_json: Json;
          blocked: boolean;
          blocked_reason: string | null;
          executed: boolean;
          reason_json: Json;
        };
      };
      strategy_configs: {
        Row: {
          id: string;
          mode: "paper" | "live";
          name: string;
          config_json: Json;
          version: number;
          is_active: boolean;
          created_at: string;
          created_by: string;
          checksum: string;
        };
        Insert: {
          id?: string;
          mode: "paper" | "live";
          name?: string;
          config_json: Json;
          version?: number;
          is_active?: boolean;
          created_at?: string;
          created_by?: string;
          checksum: string;
        };
        Update: {
          is_active?: boolean;
        };
      };
      config_audit_log: {
        Row: {
          id: string;
          mode: "paper" | "live";
          version: number;
          changed_at: string;
          changed_by: string;
          diff_json: Json;
          reason: string | null;
          prev_config: Json;
          new_config: Json;
        };
        Insert: {
          id?: string;
          mode: "paper" | "live";
          version: number;
          changed_at?: string;
          changed_by?: string;
          diff_json: Json;
          reason?: string;
          prev_config?: Json;
          new_config?: Json;
        };
      };
    };
    Views: {
      [_ in never]: never;
    };
    Functions: {
      get_account_overview: {
        Args: { p_discord_id?: string };
        Returns: {
          account_id: string;
          equity: number;
          cash: number;
          buying_power: number;
          pdt_count: number;
          day_pnl: number;
          last_updated: string;
        }[];
      };
      get_positions_report: {
        Args: { p_account_id?: string };
        Returns: {
          symbol: string;
          quantity: number;
          avg_price: number;
          current_price: number;
          market_value: number;
          unrealized_pnl: number;
          pnl_percent: number;
        }[];
      };
      get_activity_feed: {
        Args: { p_limit?: number };
        Returns: {
          type: "TRADE" | "SYSTEM";
          symbol: string;
          details: string;
          event_ts: string;
        }[];
      };
    };
    Enums: {
      [_ in never]: never;
    };
    CompositeTypes: {
      [_ in never]: never;
    };
  };
}
