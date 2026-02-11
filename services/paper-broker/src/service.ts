/**
 * PaperBrokerService — Full paper execution engine.
 * Handles order submission, fill simulation, position tracking, and P&L.
 * All state persisted to Supabase.
 */
import { createLogger } from "../../shared/src/logger.js";
import { getDb, auditLog } from "../../shared/src/db.js";
import type {
  Account,
  Order,
  Fill,
  Trade,
  Position,
  Quote,
  DayTrade,
  PDTStatus,
  OrderSide,
} from "../../shared/src/types.js";
import { checkOrderRisk, type RiskConfig } from "./risk-manager.js";
import { calculateFillPrice, type SlippageConfig } from "./slippage.js";
import { checkPDT, createDayTradeRecord, type PDTConfig } from "./pdt-limiter.js";

const log = createLogger("paper-broker");

export interface PaperBrokerConfig {
  startingEquity: number;
  slippage: SlippageConfig;
  risk: Partial<RiskConfig>;
  pdt: PDTConfig;
}

const DEFAULT_CONFIG: PaperBrokerConfig = {
  startingEquity: 2000,
  slippage: { pessimisticFills: true, slippageBps: 5 },
  risk: {},
  pdt: { maxDayTrades: 3, windowDays: 5 },
};

export interface OrderRequest {
  accountId: string;
  symbol: string;
  side: OrderSide;
  quantity: number;
  limitPrice?: number;
  strategy?: string;
  strategyVersion?: string;
  isDayTrade?: boolean;
  legs?: Array<{ symbol: string; side: OrderSide; ratio: number }>;
  meta?: Record<string, unknown>;
}

export type OrderResult =
  | { status: "filled"; fill: Fill; order: Order }
  | { status: "rejected"; reason: string };

export class PaperBrokerService {
  private config: PaperBrokerConfig;

  constructor(config: Partial<PaperBrokerConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    log.info("PaperBrokerService initialized", {
      startingEquity: this.config.startingEquity,
      pessimistic: this.config.slippage.pessimisticFills,
    });
  }

  // ─── Account Operations ─────────────────────────────────────────────

  async getAccount(accountId: string): Promise<Account | null> {
    try {
      const db = getDb();
      const { data, error } = await db
        .from("accounts")
        .select("*")
        .eq("id", accountId)
        .single();

      if (error) {
        log.error("Failed to fetch account", { accountId, error: error.message });
        return null;
      }

      return data as Account;
    } catch (e) {
      log.error("getAccount error", { error: String(e) });
      return null;
    }
  }

  async getOrCreateAccount(userId: string, instanceId = "default"): Promise<Account | null> {
    try {
      const db = getDb();

      // Try to find existing
      const { data: existing } = await db
        .from("accounts")
        .select("*")
        .eq("user_id", userId)
        .eq("instance_id", instanceId)
        .single();

      if (existing) return existing as Account;

      // Create new account
      const { data: created, error } = await db
        .from("accounts")
        .insert({
          user_id: userId,
          instance_id: instanceId,
          equity: this.config.startingEquity,
          cash: this.config.startingEquity,
          buying_power: this.config.startingEquity,
          pdt_count: 0,
          day_trades_history: [],
        })
        .select()
        .single();

      if (error) {
        log.error("Failed to create account", { error: error.message });
        return null;
      }

      log.info("New paper account created", { userId, instanceId, equity: this.config.startingEquity });
      return created as Account;
    } catch (e) {
      log.error("getOrCreateAccount error", { error: String(e) });
      return null;
    }
  }

  // ─── Order Submission ───────────────────────────────────────────────

  async submitOrder(req: OrderRequest, quote: Quote): Promise<OrderResult> {
    const db = getDb();

    // 1. Fetch account
    const account = await this.getAccount(req.accountId);
    if (!account) {
      return { status: "rejected", reason: "Account not found" };
    }

    // 2. Fetch open positions
    const positions = await this.getPositions(req.accountId);

    // 3. Risk check
    const riskCheck = checkOrderRisk(
      account,
      {
        symbol: req.symbol,
        side: req.side,
        quantity: req.quantity,
        price: req.limitPrice ?? quote.price,
      },
      positions,
      req.isDayTrade ?? false,
      { ...this.config.risk, pdtConfig: this.config.pdt }
    );

    if (!riskCheck.allowed) {
      log.tradeDecision("ORDER_REJECTED", {
        symbol: req.symbol,
        side: req.side,
        reason: riskCheck.reason,
      });
      await auditLog("order_rejected", {
        accountId: req.accountId,
        symbol: req.symbol,
        reason: riskCheck.reason,
      });
      return { status: "rejected", reason: riskCheck.reason! };
    }

    // 4. Calculate fill price
    const fillResult = calculateFillPrice(req.side, quote, this.config.slippage);

    // 5. Check limit price
    if (req.limitPrice !== undefined) {
      if (req.side === "buy" && fillResult.fillPrice > req.limitPrice) {
        return {
          status: "rejected",
          reason: `Fill price $${fillResult.fillPrice} exceeds limit $${req.limitPrice}`,
        };
      }
      if (req.side === "sell" && fillResult.fillPrice < req.limitPrice) {
        return {
          status: "rejected",
          reason: `Fill price $${fillResult.fillPrice} below limit $${req.limitPrice}`,
        };
      }
    }

    const now = new Date().toISOString();
    const cost = fillResult.fillPrice * req.quantity * 100; // options multiplier

    // 6. Create trade record
    const { data: trade, error: tradeError } = await db
      .from("trades")
      .insert({
        account_id: req.accountId,
        symbol: req.symbol,
        strategy: req.strategy ?? "manual",
        strategy_version: req.strategyVersion ?? "1.0.0",
        status: req.side === "buy" ? "open" : "closed",
        entry_time: now,
        entry_price: fillResult.fillPrice,
        quantity: req.quantity,
        legs: req.legs ?? [{ symbol: req.symbol, side: req.side, ratio: 1 }],
      })
      .select("id")
      .single();

    if (tradeError) {
      log.error("Failed to create trade", { error: tradeError.message });
      return { status: "rejected", reason: `DB error: ${tradeError.message}` };
    }

    // 7. Create order record
    const { data: order, error: orderError } = await db
      .from("orders")
      .insert({
        trade_id: trade.id,
        account_id: req.accountId,
        symbol: req.symbol,
        side: req.side,
        type: req.limitPrice ? "limit" : "market",
        price: fillResult.fillPrice,
        quantity: req.quantity,
        status: "filled",
        created_at: now,
        filled_at: now,
        filled_price: fillResult.fillPrice,
        slippage_bps: fillResult.slippageBps,
        legs: req.legs ?? [{ symbol: req.symbol, side: req.side, ratio: 1 }],
        meta: req.meta ?? null,
      })
      .select()
      .single();

    if (orderError) {
      log.error("Failed to create order", { error: orderError.message });
      return { status: "rejected", reason: `DB error: ${orderError.message}` };
    }

    // 8. Create fill record
    const { data: fill, error: fillError } = await db
      .from("fills")
      .insert({
        order_id: order.id,
        trade_id: trade.id,
        timestamp: now,
        symbol: req.symbol,
        side: req.side,
        quantity: req.quantity,
        price: fillResult.fillPrice,
        slippage: fillResult.slippageAmount,
        fee: 0,
      })
      .select()
      .single();

    if (fillError) {
      log.error("Failed to create fill", { error: fillError.message });
      return { status: "rejected", reason: `DB error: ${fillError.message}` };
    }

    // 9. Update account state
    if (req.side === "buy") {
      await db
        .from("accounts")
        .update({
          cash: account.cash - cost,
          buying_power: account.buying_power - cost,
          updated_at: now,
        })
        .eq("id", req.accountId);
    } else {
      await db
        .from("accounts")
        .update({
          cash: account.cash + cost,
          buying_power: account.buying_power + cost,
          updated_at: now,
        })
        .eq("id", req.accountId);
    }

    // 10. Upsert position
    if (req.side === "buy") {
      const existing = positions.find((p) => p.symbol === req.symbol);
      if (existing) {
        const newQty = existing.quantity + req.quantity;
        const newAvg =
          (existing.avg_price * existing.quantity + fillResult.fillPrice * req.quantity) /
          newQty;
        await db
          .from("positions")
          .update({
            quantity: newQty,
            avg_price: Number(newAvg.toFixed(4)),
            current_price: fillResult.fillPrice,
            market_value: Number((newQty * fillResult.fillPrice * 100).toFixed(2)),
            updated_at: now,
          })
          .eq("id", existing.id);
      } else {
        await db.from("positions").insert({
          account_id: req.accountId,
          symbol: req.symbol,
          underlying: req.symbol.split(/\d/)[0], // best-effort extraction
          quantity: req.quantity,
          avg_price: fillResult.fillPrice,
          current_price: fillResult.fillPrice,
          market_value: Number((req.quantity * fillResult.fillPrice * 100).toFixed(2)),
        });
      }
    } else {
      // Selling: reduce or close position
      const existing = positions.find((p) => p.symbol === req.symbol);
      if (existing) {
        const newQty = existing.quantity - req.quantity;
        if (newQty <= 0) {
          await db.from("positions").delete().eq("id", existing.id);
        } else {
          await db
            .from("positions")
            .update({
              quantity: newQty,
              current_price: fillResult.fillPrice,
              market_value: Number((newQty * fillResult.fillPrice * 100).toFixed(2)),
              updated_at: now,
            })
            .eq("id", existing.id);
        }
      }
    }

    // 11. Log trade decision
    log.tradeDecision("ORDER_FILLED", {
      tradeId: trade.id,
      symbol: req.symbol,
      side: req.side,
      quantity: req.quantity,
      fillPrice: fillResult.fillPrice,
      slippageBps: fillResult.slippageBps,
      strategy: req.strategy ?? "manual",
    });

    await auditLog("order_filled", {
      tradeId: trade.id,
      orderId: order.id,
      fillId: fill.id,
      symbol: req.symbol,
      side: req.side,
      quantity: req.quantity,
      price: fillResult.fillPrice,
    });

    return {
      status: "filled",
      fill: fill as Fill,
      order: order as Order,
    };
  }

  // ─── Position Queries ───────────────────────────────────────────────

  async getPositions(accountId: string): Promise<Position[]> {
    try {
      const db = getDb();
      const { data, error } = await db
        .from("positions")
        .select("*")
        .eq("account_id", accountId);

      if (error) {
        log.error("Failed to fetch positions", { error: error.message });
        return [];
      }

      return (data ?? []) as Position[];
    } catch (e) {
      log.error("getPositions error", { error: String(e) });
      return [];
    }
  }

  async getTrades(
    accountId: string,
    opts?: { status?: string; limit?: number }
  ): Promise<Trade[]> {
    try {
      const db = getDb();
      let query = db
        .from("trades")
        .select("*")
        .eq("account_id", accountId)
        .order("entry_time", { ascending: false });

      if (opts?.status) query = query.eq("status", opts.status);
      if (opts?.limit) query = query.limit(opts.limit);

      const { data, error } = await query;

      if (error) {
        log.error("Failed to fetch trades", { error: error.message });
        return [];
      }

      return (data ?? []) as Trade[];
    } catch (e) {
      log.error("getTrades error", { error: String(e) });
      return [];
    }
  }

  // ─── PDT Status ─────────────────────────────────────────────────────

  async getPDTStatus(accountId: string): Promise<PDTStatus> {
    const account = await this.getAccount(accountId);
    if (!account) {
      return {
        day_trade_count: 0,
        max_allowed: this.config.pdt.maxDayTrades,
        trades_in_window: [],
        can_day_trade: true,
        next_expiry: null,
      };
    }
    return checkPDT(account.day_trades_history, this.config.pdt);
  }

  // ─── Account Summary ───────────────────────────────────────────────

  async getAccountSummary(accountId: string): Promise<{
    equity: number;
    cash: number;
    buying_power: number;
    pnl_today: number;
    pnl_total: number;
    open_positions: number;
  } | null> {
    const account = await this.getAccount(accountId);
    if (!account) return null;

    const positions = await this.getPositions(accountId);
    const openPnL = positions.reduce((sum, p) => {
      if (p.current_price && p.avg_price) {
        return sum + (p.current_price - p.avg_price) * p.quantity * 100;
      }
      return sum;
    }, 0);

    const equity = account.cash + openPnL;
    const pnlTotal = equity - this.config.startingEquity;

    return {
      equity: Number(equity.toFixed(2)),
      cash: Number(account.cash),
      buying_power: Number(account.buying_power),
      pnl_today: 0, // TODO: calculate from daily_pnl table
      pnl_total: Number(pnlTotal.toFixed(2)),
      open_positions: positions.length,
    };
  }
}
