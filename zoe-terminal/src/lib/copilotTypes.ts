/** Canonical FeedItem — every event in the copilot sidebar is rendered from this. */
export interface FeedItem {
  id: string;
  source: 'chat' | 'thought' | 'system' | 'trade' | 'config';
  subtype: string;
  severity: 'info' | 'success' | 'warning' | 'critical';
  title: string;
  body: string | null;
  symbol: string | null;
  color_hint: string | null;
  metadata: Record<string, unknown>;
  mode: 'paper' | 'live';
  created_at: string;
}

/** Filter state for the feed panel. */
export interface FeedFilter {
  sources: Set<FeedItem['source']>;
  symbol: string;
  severity: FeedItem['severity'] | 'all';
}

/** Chat message within the copilot. */
export interface CopilotMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  streaming?: boolean;
}

/** Source badge config — color and label for each source type. */
export const SOURCE_CONFIG: Record<FeedItem['source'], { label: string; color: string }> = {
  chat:    { label: 'Chat',    color: 'text-white' },
  thought: { label: 'Thought', color: 'text-text-muted' },
  system:  { label: 'System',  color: 'text-yellow-400' },
  trade:   { label: 'Trade',   color: 'text-blue-400' },
  config:  { label: 'Config',  color: 'text-text-secondary' },
};

/** Subtype → color mapping for trade events (strict: GREEN = gains, RED = losses only). */
export function getTradeChipColor(subtype: string, pnl?: number): string {
  if (subtype === 'BUY_FILLED') return 'text-blue-400';
  if (subtype === 'SELL_FILLED') return 'text-text-secondary';
  if (subtype === 'PNL_REALIZED') {
    if (pnl != null && pnl > 0) return 'text-profit';
    if (pnl != null && pnl < 0) return 'text-loss';
    return 'text-text-muted';
  }
  return 'text-text-muted';
}
