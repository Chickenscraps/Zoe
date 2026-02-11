/**
 * @zoe/paper-broker — Execution simulation, fills, PDT/day-trade limiter
 */
export { PaperBrokerService, type PaperBrokerConfig, type OrderRequest, type OrderResult } from "./service.js";
export { checkPDT, getWindowStartDate, getTradesInWindow, createDayTradeRecord, type PDTConfig } from "./pdt-limiter.js";
export { calculateFillPrice, estimateSlippage, type SlippageConfig, type FillResult } from "./slippage.js";
export { checkOrderRisk, type RiskConfig, type RiskCheckResult } from "./risk-manager.js";
