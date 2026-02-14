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
        Insert: {
          id?: string;
          account_id: string;
          symbol: string;
          underlying?: string | null;
          quantity: number;
          avg_price: number;
          current_price: number;
          market_value: number;
          updated_at?: string;
        };
        Update: {
          id?: string;
          account_id?: string;
          symbol?: string;
          underlying?: string | null;
          quantity?: number;
          avg_price?: number;
          current_price?: number;
          market_value?: number;
          updated_at?: string;
        };
        Relationships: [];
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
        Insert: {
          trade_id?: string;
          instance_id: string;
          symbol: string;
          strategy: string;
          opened_at?: string;
          closed_at?: string | null;
          realized_pnl?: number;
          r_multiple?: number | null;
          outcome?: "win" | "loss" | "scratch" | "open";
          rationale?: string | null;
        };
        Update: {
          trade_id?: string;
          instance_id?: string;
          symbol?: string;
          strategy?: string;
          opened_at?: string;
          closed_at?: string | null;
          realized_pnl?: number;
          r_multiple?: number | null;
          outcome?: "win" | "loss" | "scratch" | "open";
          rationale?: string | null;
        };
        Relationships: [];
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
        };
        Insert: {
          date: string;
          instance_id: string;
          daily_pnl?: number;
          equity?: number;
          drawdown?: number;
          win_rate?: number | null;
          expectancy?: number | null;
          cash_buffer_pct?: number;
          day_trades_used?: number;
          realized_pnl?: number;
          unrealized_pnl?: number;
        };
        Update: {
          date?: string;
          instance_id?: string;
          daily_pnl?: number;
          equity?: number;
          drawdown?: number;
          win_rate?: number | null;
          expectancy?: number | null;
          cash_buffer_pct?: number;
          day_trades_used?: number;
          realized_pnl?: number;
          unrealized_pnl?: number;
        };
        Relationships: [];
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
        };
        Insert: {
          id?: string;
          instance_id: string;
          symbol: string;
          score: number;
          score_breakdown?: Json;
          info?: Json;
          recommended_strategy: string;
          created_at?: string;
        };
        Update: {
          id?: string;
          instance_id?: string;
          symbol?: string;
          score?: number;
          score_breakdown?: Json;
          info?: Json;
          recommended_strategy?: string;
          created_at?: string;
        };
        Relationships: [];
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
        };
        Insert: {
          id?: string;
          instance_id: string;
          content: string;
          type: "scan" | "entry" | "exit" | "health" | "general";
          symbol?: string | null;
          created_at?: string;
          metadata?: Json;
        };
        Update: {
          id?: string;
          instance_id?: string;
          content?: string;
          type?: "scan" | "entry" | "exit" | "health" | "general";
          symbol?: string | null;
          created_at?: string;
          metadata?: Json;
        };
        Relationships: [];
      };
      health_heartbeat: {
        Row: {
          id: string;
          instance_id: string;
          component: string;
          status: "ok" | "warning" | "error" | "down";
          last_heartbeat: string;
          details: Json;
        };
        Insert: {
          id?: string;
          instance_id: string;
          component: string;
          status: "ok" | "warning" | "error" | "down";
          last_heartbeat?: string;
          details?: Json;
        };
        Update: {
          id?: string;
          instance_id?: string;
          component?: string;
          status?: "ok" | "warning" | "error" | "down";
          last_heartbeat?: string;
          details?: Json;
        };
        Relationships: [];
      };
      daily_gameplans: {
        Row: {
          id: string;
          instance_id: string;
          date: string;
          status: "draft" | "refined" | "locked";
          created_at: string;
        };
        Insert: {
          id?: string;
          instance_id: string;
          date: string;
          status?: "draft" | "refined" | "locked";
          created_at?: string;
        };
        Update: {
          id?: string;
          instance_id?: string;
          date?: string;
          status?: "draft" | "refined" | "locked";
          created_at?: string;
        };
        Relationships: [];
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
        Insert: {
          id?: string;
          plan_id: string;
          symbol: string;
          catalyst_summary?: string | null;
          regime?: string | null;
          ivr_tech_snapshot?: string | null;
          preferred_strategy?: string | null;
          risk_tier?: string | null;
          do_not_trade?: boolean;
          visual_notes?: string | null;
        };
        Update: {
          id?: string;
          plan_id?: string;
          symbol?: string;
          catalyst_summary?: string | null;
          regime?: string | null;
          ivr_tech_snapshot?: string | null;
          preferred_strategy?: string | null;
          risk_tier?: string | null;
          do_not_trade?: boolean;
          visual_notes?: string | null;
        };
        Relationships: [];
      };
      config: {
        Row: {
          key: string;
          instance_id: string;
          value: Json;
        };
        Insert: {
          key: string;
          instance_id?: string;
          value: Json;
        };
        Update: {
          key?: string;
          instance_id?: string;
          value?: Json;
        };
        Relationships: [];
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
        Insert: {
          id?: string;
          instance_id?: string;
          event_type: string;
          message?: string;
          created_at?: string;
          metadata?: Json;
        };
        Update: {
          id?: string;
          instance_id?: string;
          event_type?: string;
          message?: string;
          created_at?: string;
          metadata?: Json;
        };
        Relationships: [];
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
        Insert: {
          id?: string;
          instance_id?: string;
          event_type: string;
          severity: "info" | "warning" | "critical";
          message: string;
          created_at?: string;
        };
        Update: {
          id?: string;
          instance_id?: string;
          event_type?: string;
          severity?: "info" | "warning" | "critical";
          message?: string;
          created_at?: string;
        };
        Relationships: [];
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
          limit_price: number | null;
          status: "new" | "submitted" | "partially_filled" | "filled" | "canceled" | "rejected" | "cancel_pending" | "working";
          requested_at: string;
          submitted_at: string | null;
          updated_at: string;
          raw_response: Json;
        };
        Insert: {
          id?: string;
          client_order_id: string;
          symbol: string;
          side: "buy" | "sell";
          order_type: "market" | "limit";
          qty?: number | null;
          notional?: number | null;
          status?: "new" | "submitted" | "partially_filled" | "filled" | "canceled" | "rejected";
          requested_at?: string;
          submitted_at?: string | null;
          updated_at?: string;
          raw_response?: Json;
        };
        Update: {
          id?: string;
          client_order_id?: string;
          symbol?: string;
          side?: "buy" | "sell";
          order_type?: "market" | "limit";
          qty?: number | null;
          notional?: number | null;
          status?: "new" | "submitted" | "partially_filled" | "filled" | "canceled" | "rejected";
          requested_at?: string;
          submitted_at?: string | null;
          updated_at?: string;
          raw_response?: Json;
        };
        Relationships: [];
      };
      crypto_tickers: {
        Row: {
          symbol: string;
          price: number;
          change_24h: number | null;
          last_updated: string;
        };
        Insert: {
          symbol: string;
          price: number;
          change_24h?: number | null;
          last_updated?: string;
        };
        Update: {
          symbol?: string;
          price?: number;
          change_24h?: number | null;
          last_updated?: string;
        };
        Relationships: [];
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
        };
        Insert: {
          id?: string;
          order_id: string;
          fill_id: string;
          symbol: string;
          side: "buy" | "sell";
          qty: number;
          price: number;
          fee?: number;
          executed_at?: string;
          raw_fill?: Json;
        };
        Update: {
          id?: string;
          order_id?: string;
          fill_id?: string;
          symbol?: string;
          side?: "buy" | "sell";
          qty?: number;
          price?: number;
          fee?: number;
          executed_at?: string;
          raw_fill?: Json;
        };
        Relationships: [];
      };
      crypto_holdings_snapshots: {
        Row: {
          id: string;
          taken_at: string;
          holdings: Json;
          total_crypto_value: number;
          source: string;
        };
        Insert: {
          id?: string;
          taken_at?: string;
          holdings: Json;
          total_crypto_value: number;
          source: string;
        };
        Update: {
          id?: string;
          taken_at?: string;
          holdings?: Json;
          total_crypto_value?: number;
          source?: string;
        };
        Relationships: [];
      };
      crypto_cash_snapshots: {
        Row: {
          id: string;
          taken_at: string;
          cash_available: number;
          buying_power: number;
          source: string;
        };
        Insert: {
          id?: string;
          taken_at?: string;
          cash_available: number;
          buying_power: number;
          source: string;
        };
        Update: {
          id?: string;
          taken_at?: string;
          cash_available?: number;
          buying_power?: number;
          source?: string;
        };
        Relationships: [];
      };
      daily_notional: {
        Row: {
          day: string;
          amount: number;
          notional_used: number;
          notional_limit: number;
        };
        Insert: {
          day: string;
          amount?: number;
          notional_used?: number;
          notional_limit?: number;
        };
        Update: {
          day?: string;
          amount?: number;
          notional_used?: number;
          notional_limit?: number;
        };
        Relationships: [];
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
          created_at: string;
        };
        Insert: {
          id?: number;
          symbol: string;
          timeframe: string;
          open_time: number;
          open: number;
          high: number;
          low: number;
          close: number;
          volume: number;
          patterns?: Json;
          created_at?: string;
        };
        Update: {
          id?: number;
          symbol?: string;
          timeframe?: string;
          open_time?: number;
          open?: number;
          high?: number;
          low?: number;
          close?: number;
          volume?: number;
          patterns?: Json;
          created_at?: string;
        };
        Relationships: [];
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
        Insert: {
          id?: string;
          symbol: string;
          feature_name: string;
          value: number;
          computed_at?: string;
          source: string;
          metadata?: Json;
        };
        Update: {
          id?: string;
          symbol?: string;
          feature_name?: string;
          value?: number;
          computed_at?: string;
          source?: string;
          metadata?: Json;
        };
        Relationships: [];
      };
      ef_regimes: {
        Row: {
          id: string;
          regime: string;
          confidence: number;
          detected_at: string;
          features_used: Json;
        };
        Insert: {
          id?: string;
          regime: string;
          confidence: number;
          detected_at?: string;
          features_used?: Json;
        };
        Update: {
          id?: string;
          regime?: string;
          confidence?: number;
          detected_at?: string;
          features_used?: Json;
        };
        Relationships: [];
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
        Insert: {
          id?: string;
          symbol: string;
          direction: string;
          strength: number;
          regime_id?: string | null;
          features?: Json;
          generated_at?: string;
          strategy_name: string;
          acted_on?: boolean;
        };
        Update: {
          id?: string;
          symbol?: string;
          direction?: string;
          strength?: number;
          regime_id?: string | null;
          features?: Json;
          generated_at?: string;
          strategy_name?: string;
          acted_on?: boolean;
        };
        Relationships: [];
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
        Insert: {
          id?: string;
          symbol: string;
          side: string;
          entry_price?: number | null;
          entry_time?: string | null;
          size_usd?: number | null;
          tp_price?: number | null;
          sl_price?: number | null;
          status: string;
          exit_price?: number | null;
          exit_time?: string | null;
          pnl_usd?: number | null;
          signal_id?: string | null;
          order_id?: string | null;
          created_at?: string;
        };
        Update: {
          id?: string;
          symbol?: string;
          side?: string;
          entry_price?: number | null;
          entry_time?: string | null;
          size_usd?: number | null;
          tp_price?: number | null;
          sl_price?: number | null;
          status?: string;
          exit_price?: number | null;
          exit_time?: string | null;
          pnl_usd?: number | null;
          signal_id?: string | null;
          order_id?: string | null;
          created_at?: string;
        };
        Relationships: [];
      };
      ef_state: {
        Row: {
          key: string;
          value: Json;
          updated_at: string;
        };
        Insert: {
          key: string;
          value: Json;
          updated_at?: string;
        };
        Update: {
          key?: string;
          value?: Json;
          updated_at?: string;
        };
        Relationships: [];
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
        Insert: {
          id?: number;
          symbol: string;
          timeframe: string;
          timestamp: string;
          price: number;
          type: "high" | "low";
          source: "wick" | "body";
          atr_snapshot?: number | null;
          confirmed?: boolean;
          created_at?: string;
        };
        Update: {
          id?: number;
          symbol?: string;
          timeframe?: string;
          timestamp?: string;
          price?: number;
          type?: "high" | "low";
          source?: "wick" | "body";
          atr_snapshot?: number | null;
          confirmed?: boolean;
          created_at?: string;
        };
        Relationships: [];
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
        Insert: {
          id?: number;
          symbol: string;
          timeframe: string;
          side: "support" | "resistance";
          slope: number;
          intercept: number;
          start_at: string;
          end_at: string;
          inlier_count?: number;
          score?: number;
          metadata?: Json;
          is_active?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: number;
          symbol?: string;
          timeframe?: string;
          side?: "support" | "resistance";
          slope?: number;
          intercept?: number;
          start_at?: string;
          end_at?: string;
          inlier_count?: number;
          score?: number;
          metadata?: Json;
          is_active?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Relationships: [];
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
        Insert: {
          id?: number;
          symbol: string;
          timeframe: string;
          price_centroid: number;
          price_top: number;
          price_bottom: number;
          role?: "support" | "resistance" | "flip" | null;
          touch_count?: number;
          score?: number;
          first_tested?: string | null;
          last_tested?: string | null;
          is_active?: boolean;
          metadata?: Json;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: number;
          symbol?: string;
          timeframe?: string;
          price_centroid?: number;
          price_top?: number;
          price_bottom?: number;
          role?: "support" | "resistance" | "flip" | null;
          touch_count?: number;
          score?: number;
          first_tested?: string | null;
          last_tested?: string | null;
          is_active?: boolean;
          metadata?: Json;
          created_at?: string;
          updated_at?: string;
        };
        Relationships: [];
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
        Insert: {
          id?: number;
          symbol: string;
          timeframe: string;
          event_type: "breakout" | "breakdown" | "retest";
          reference_id?: number | null;
          reference_kind?: "trendline" | "level" | null;
          price_at: number;
          confirmed?: boolean;
          confirm_count?: number;
          reason_json?: Json;
          ts: string;
        };
        Update: {
          id?: number;
          symbol?: string;
          timeframe?: string;
          event_type?: "breakout" | "breakdown" | "retest";
          reference_id?: number | null;
          reference_kind?: "trendline" | "level" | null;
          price_at?: number;
          confirmed?: boolean;
          confirm_count?: number;
          reason_json?: Json;
          ts?: string;
        };
        Relationships: [];
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
        Insert: {
          id?: string;
          ts: string;
          symbol: string;
          prev_state?: string | null;
          state: string;
          score?: number | null;
          reason_json?: Json;
        };
        Update: {
          id?: string;
          ts?: string;
          symbol?: string;
          prev_state?: string | null;
          state?: string;
          score?: number | null;
          reason_json?: Json;
        };
        Relationships: [];
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
        Insert: {
          id?: string;
          ts: string;
          symbol: string;
          entry_style?: "retest" | "breakout" | null;
          entry_price?: number | null;
          expected_move_pct?: number | null;
          tp_price?: number | null;
          sl_price?: number | null;
          score?: number | null;
          components_json?: Json;
          blocked?: boolean;
          blocked_reason?: string | null;
          executed?: boolean;
          reason_json?: Json;
        };
        Update: {
          id?: string;
          ts?: string;
          symbol?: string;
          entry_style?: "retest" | "breakout" | null;
          entry_price?: number | null;
          expected_move_pct?: number | null;
          tp_price?: number | null;
          sl_price?: number | null;
          score?: number | null;
          components_json?: Json;
          blocked?: boolean;
          blocked_reason?: string | null;
          executed?: boolean;
          reason_json?: Json;
        };
        Relationships: [];
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
          created_at: string;
        };
        Insert: {
          id?: string;
          source: "chat" | "thought" | "system" | "trade" | "config";
          subtype: string;
          severity: "info" | "success" | "warning" | "critical";
          title: string;
          body?: string | null;
          symbol?: string | null;
          color_hint?: string | null;
          metadata?: Json;
          created_at?: string;
        };
        Update: {
          id?: string;
          source?: "chat" | "thought" | "system" | "trade" | "config";
          subtype?: string;
          severity?: "info" | "success" | "warning" | "critical";
          title?: string;
          body?: string | null;
          symbol?: string | null;
          color_hint?: string | null;
          metadata?: Json;
          created_at?: string;
        };
        Relationships: [];
      };
      copilot_messages: {
        Row: {
          id: string;
          user_id: string;
          role: "user" | "assistant";
          content: string;
          context_page: string | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          user_id: string;
          role: "user" | "assistant";
          content: string;
          context_page?: string | null;
          created_at?: string;
        };
        Update: {
          id?: string;
          user_id?: string;
          role?: "user" | "assistant";
          content?: string;
          context_page?: string | null;
          created_at?: string;
        };
        Relationships: [];
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
          locked_at: string;
          lock_holder: string;
          ttl_seconds: number;
          instance_id: string;
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
