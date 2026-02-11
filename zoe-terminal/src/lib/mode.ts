/**
 * Build-time mode lock. Set via VITE_MODE_LOCK env var.
 * Paper = simulated data only. Live = real broker data.
 * There is no runtime toggle — mode is frozen at build time.
 */

export type TradingMode = 'paper' | 'live';

const raw = import.meta.env.VITE_MODE_LOCK ?? 'paper';
export const MODE: TradingMode = raw === 'live' ? 'live' : 'paper';

export const isPaper = MODE === 'paper';
export const isLive = MODE === 'live';

/** Guard: throws if mode is not paper (for dev/write operations). */
export function requirePaperForWrite(): void {
  if (!isPaper) {
    throw new Error('Write operations are only allowed in paper mode');
  }
}
