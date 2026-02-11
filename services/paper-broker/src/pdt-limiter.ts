/**
 * PDT (Pattern Day Trader) Limiter
 * Enforces: max 3 day trades per rolling 5 TRADING days.
 * A "day trade" = opening AND closing the same position in the same session.
 */
import { isTradingDay } from "../../shared/src/market-session.js";
import { createLogger } from "../../shared/src/logger.js";
import type { DayTrade, PDTStatus } from "../../shared/src/types.js";

const log = createLogger("pdt-limiter");

export interface PDTConfig {
  maxDayTrades: number;  // default 3
  windowDays: number;    // default 5 (trading days, not calendar days)
}

const DEFAULT_CONFIG: PDTConfig = {
  maxDayTrades: 3,
  windowDays: 5,
};

/**
 * Count the number of trading days going back from a given date.
 * Returns the calendar date that is `tradingDays` trading days ago.
 */
export function getWindowStartDate(
  fromDate: Date,
  tradingDaysBack: number
): Date {
  const d = new Date(fromDate);
  let counted = 0;

  while (counted < tradingDaysBack) {
    d.setDate(d.getDate() - 1);
    if (isTradingDay(d)) {
      counted++;
    }
  }

  // Set to start of day
  d.setHours(0, 0, 0, 0);
  return d;
}

/**
 * Filter day trades to only those within the rolling window.
 */
export function getTradesInWindow(
  trades: DayTrade[],
  windowStart: Date
): DayTrade[] {
  const windowMs = windowStart.getTime();
  return trades.filter((t) => {
    const closeTime = new Date(t.close_time).getTime();
    return closeTime >= windowMs;
  });
}

/**
 * Find when the oldest day trade in the window will expire
 * (i.e., fall outside the 5-trading-day window).
 */
export function getNextExpiry(
  tradesInWindow: DayTrade[],
  windowDays: number
): string | null {
  if (tradesInWindow.length === 0) return null;

  // Find the oldest trade
  const sorted = [...tradesInWindow].sort(
    (a, b) => new Date(a.close_time).getTime() - new Date(b.close_time).getTime()
  );
  const oldest = sorted[0]!;

  // The oldest trade will expire when `windowDays` trading days pass from it
  const oldestDate = new Date(oldest.close_time);
  let counted = 0;
  const d = new Date(oldestDate);

  while (counted < windowDays) {
    d.setDate(d.getDate() + 1);
    if (isTradingDay(d)) {
      counted++;
    }
  }

  return d.toISOString();
}

/**
 * Check PDT status for an account.
 */
export function checkPDT(
  dayTradesHistory: DayTrade[],
  config: Partial<PDTConfig> = {}
): PDTStatus {
  const cfg = { ...DEFAULT_CONFIG, ...config };
  const now = new Date();
  const windowStart = getWindowStartDate(now, cfg.windowDays);
  const tradesInWindow = getTradesInWindow(dayTradesHistory, windowStart);
  const count = tradesInWindow.length;
  const canTrade = count < cfg.maxDayTrades;

  const nextExpiry = canTrade
    ? null
    : getNextExpiry(tradesInWindow, cfg.windowDays);

  if (!canTrade) {
    log.warn("PDT limit reached", {
      count,
      max: cfg.maxDayTrades,
      nextExpiry,
    });
  }

  return {
    day_trade_count: count,
    max_allowed: cfg.maxDayTrades,
    trades_in_window: tradesInWindow,
    can_day_trade: canTrade,
    next_expiry: nextExpiry,
  };
}

/**
 * Create a new day trade record.
 */
export function createDayTradeRecord(
  tradeId: string,
  symbol: string,
  openTime: string,
  closeTime: string,
  pnl: number
): DayTrade {
  return {
    trade_id: tradeId,
    symbol,
    open_time: openTime,
    close_time: closeTime,
    pnl,
  };
}
