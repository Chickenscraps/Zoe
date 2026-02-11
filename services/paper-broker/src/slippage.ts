/**
 * Slippage Model for Paper Broker
 * Simulates realistic fill prices based on bid/ask spread and configurable slippage.
 */
import type { Quote, OrderSide } from "../../shared/src/types.js";

export interface SlippageConfig {
  pessimisticFills: boolean; // true = cross spread + slippage
  slippageBps: number;       // basis points (5 = 0.05%)
}

export interface FillResult {
  fillPrice: number;
  slippageBps: number;
  slippageAmount: number;
}

const DEFAULT_CONFIG: SlippageConfig = {
  pessimisticFills: true,
  slippageBps: 5,
};

/**
 * Calculate the fill price based on quote, side, and slippage config.
 *
 * Pessimistic fills (default — more realistic):
 *   BUY  → fill at ASK + slippage
 *   SELL → fill at BID - slippage
 *
 * Optimistic fills:
 *   BUY  → fill at MID
 *   SELL → fill at MID
 */
export function calculateFillPrice(
  side: OrderSide,
  quote: Quote,
  config: Partial<SlippageConfig> = {}
): FillResult {
  const cfg = { ...DEFAULT_CONFIG, ...config };
  const mid = (quote.bid + quote.ask) / 2 || quote.price;
  const slippageMultiplier = cfg.slippageBps / 10_000;

  let basePrice: number;
  let slippageDirection: number;

  if (cfg.pessimisticFills) {
    if (side === "buy") {
      basePrice = quote.ask || mid;
      slippageDirection = 1; // pay more
    } else {
      basePrice = quote.bid || mid;
      slippageDirection = -1; // receive less
    }
  } else {
    basePrice = mid;
    slippageDirection = side === "buy" ? 1 : -1;
  }

  const slippageAmount = basePrice * slippageMultiplier * slippageDirection;
  const fillPrice = Math.max(0.01, basePrice + slippageAmount);

  return {
    fillPrice: Number(fillPrice.toFixed(4)),
    slippageBps: cfg.slippageBps,
    slippageAmount: Number(slippageAmount.toFixed(4)),
  };
}

/**
 * Estimate slippage for larger orders (simplified model).
 * Larger orders experience more slippage due to market impact.
 */
export function estimateSlippage(
  baseSlippageBps: number,
  quantity: number,
  avgDailyVolume?: number
): number {
  if (!avgDailyVolume || avgDailyVolume === 0) {
    // If we don't know volume, apply a flat multiplier for quantity > 10
    const multiplier = quantity > 10 ? 1 + (quantity - 10) * 0.05 : 1;
    return Math.round(baseSlippageBps * multiplier);
  }

  // Market impact: slippage increases with participation rate
  const participationRate = (quantity * 100) / avgDailyVolume; // as percentage
  const impactMultiplier = 1 + participationRate * 2; // 1% participation → 3x slippage
  return Math.round(baseSlippageBps * impactMultiplier);
}
