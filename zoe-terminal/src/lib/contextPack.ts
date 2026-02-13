import type { useDashboardData } from '../hooks/useDashboardData';
import { formatCurrency } from './utils';

type DashboardData = ReturnType<typeof useDashboardData>;

/**
 * Build a compact context pack (~200 tokens) injected into the copilot system prompt.
 * Summarizes key dashboard state for the current page.
 */
export function buildContextPack(pathname: string, data: DashboardData): string {
  const lines: string[] = [];

  const PAGE_NAMES: Record<string, string> = {
    '/': 'Overview', '/positions': 'Positions', '/trades': 'Trades',
    '/scanner': 'Scanner', '/charts': 'Charts', '/plan': 'Plan',
    '/thoughts': 'Thoughts', '/health': 'Health', '/settings': 'Settings',
    '/structure': 'Structure', '/consensus': 'Consensus',
  };
  lines.push(`Page: ${PAGE_NAMES[pathname] ?? pathname}`);

  const equity = data.cryptoCash?.buying_power ?? data.cryptoCash?.cash_available ?? data.accountOverview?.equity ?? 0;
  lines.push(`Equity: ${formatCurrency(equity)}`);

  if (data.holdingsRows) {
    lines.push(`Open positions: ${data.holdingsRows.length}`);
  }

  if (data.healthSummary) {
    lines.push(`System: ${data.healthSummary.status} — ${data.healthSummary.reason}`);
  }

  if (data.dailyNotional) {
    const used = (data.dailyNotional as any).notional_used ?? data.dailyNotional.amount ?? 0;
    lines.push(`Notional used: ${formatCurrency(used)}`);
  }

  return lines.join('\n');
}
