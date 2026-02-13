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
          mode: string;
          fees_paid: number;
          gross_equity: number | null;
          net_equity: number | null;
          net_deposits: number;
          crypto_value: number;
          cash_usd: number;
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
          mode: string;
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
          mode: string;
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
          mode: string;
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
          mode: string;
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
          mode: string;
          broker_fee: number;
          fee_currency: string;
          broker_fill_id: string | null;
          exchange: string;
        };
      };
      crypto_holdings_snapshots: {
        Row: {
          id: string;
          taken_at: string;
          holdings: Json;
          total_crypto_value: number;
          source: string;
          mode: string;
        };
      };
      crypto_cash_snapshots: {
        Row: {
          id: string;
          taken_at: string;
          cash_available: number;
          buying_power: number;
          source: string;
          mode: string;
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
          mode: string;
        };
      };
      daily_notional: {
        Row: {
          day: string;
          amount: number;
          notional_used: number;
          notional_limit: number;
          mode: string;
        };
      };
      agent_state: {
        Row: {
          id: string;
          mode: string;
          instance_id: string;
          state: Json;
          updated_at: string;
        };
      };
      crypto_candles: {
        Row: {
          id: number;
          symbol: string;
          timeframe: string;
          open_time: number;
          open: number;
          high: number;
          low: number;
          close: number;
          volume: number;
          patterns: Json;
          mode: string;
          created_at: string;
        };
      };
      boot_audit: {
        Row: {
          id: string;
          run_id: string;
          mode: string;
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
          mode: string;
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
          mode: string;
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
          mode: string;
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
          mode: string;
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
          mode: string;
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
          mode: string;
        };
      };
      zoe_events: {
        Row: {
          id: string;
          source: "chat" | "thought" | "system" | "trade" | "config";
          subtype: string;
          severity: "info" | "success" | "warning" | "critical";
          title: string;
          body: string | null;
          symbol: string | null;
          color_hint: string | null;
          metadata: Json;
          mode: string;
          created_at: string;
        };
      };
      copilot_messages: {
        Row: {
          id: string;
          user_id: string;
          role: "user" | "assistant";
          content: string;
          context_page: string | null;
          mode: string;
          created_at: string;
        };
      };
      market_catalog: {
        Row: {
          symbol: string;
          exchange_symbol: string;
          ws_symbol: string | null;
          base: string;
          quote: string;
          exchange: string;
          status: "active" | "delisted" | "halted";
          min_qty: number;
          lot_size: number;
          tick_size: number;
          fee_maker_pct: number;
          fee_taker_pct: number;
          ordermin: number;
          metadata: Json;
          discovered_at: string;
          updated_at: string;
        };
      };
      market_snapshot_focus: {
        Row: {
          symbol: string;
          bid: number;
          ask: number;
          mid: number;
          spread_pct: number;
          volume_24h: number;
          change_24h_pct: number;
          vwap: number;
          high_24h: number;
          low_24h: number;
          updated_at: string;
        };
      };
      market_snapshot_scout: {
        Row: {
          symbol: string;
          bid: number;
          ask: number;
          mid: number;
          volume_24h: number;
          change_24h_pct: number;
          updated_at: string;
        };
      };
      market_sparkline_points: {
        Row: {
          symbol: string;
          ts: string;
          price: number;
        };
      };
      mover_events: {
        Row: {
          id: string;
          symbol: string;
          event_type: string;
          magnitude: number;
          direction: "up" | "down";
          metadata: Json;
          detected_at: string;
        };
      };
      market_focus_config: {
        Row: {
          symbol: string;
          reason: string;
          promoted_at: string;
          expires_at: string | null;
          metadata: Json;
        };
      };
      cash_events: {
        Row: {
          id: string;
          event_type: "deposit" | "withdrawal" | "transfer_in" | "transfer_out";
          amount: number;
          currency: string;
          description: string;
          external_ref: string;
          created_at: string;
          mode: string;
        };
      };
      fee_ledger: {
        Row: {
          id: string;
          fill_id: string;
          order_id: string;
          symbol: string;
          fee_amount: number;
          fee_currency: string;
          fee_type: "trading" | "withdrawal" | "deposit" | "other";
          created_at: string;
          mode: string;
        };
      };
      order_intents: {
        Row: {
          id: string;
          idempotency_key: string;
          symbol: string;
          side: "buy" | "sell";
          order_type: "limit" | "market";
          qty: number | null;
          notional: number | null;
          limit_price: number | null;
          engine: string;
          mode: string;
          status: "created" | "submitted" | "acked" | "partial_fill" | "cancel_requested" | "cancelled" | "replaced" | "filled" | "rejected" | "expired" | "error";
          broker_order_id: string | null;
          fill_price: number | null;
          fill_qty: number | null;
          metadata: Json;
          created_at: string;
          updated_at: string;
        };
      };
      order_events: {
        Row: {
          id: string;
          intent_id: string;
          event_type: string;
          broker_order_id: string | null;
          fill_price: number | null;
          fill_qty: number | null;
          fee: number | null;
          metadata: Json;
          created_at: string;
        };
      };
      trade_locks: {
        Row: {
          symbol: string;
          engine: string;
          mode: string;
          locked_at: string;
          lock_holder: string;
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
