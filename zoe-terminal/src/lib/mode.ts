/**
 * Mode types and context re-exports.
 *
 * Runtime mode is managed by ModeContext (React context).
 * Use `useModeContext()` in components/hooks for mode access.
 */

export type { TradingMode } from './ModeContext';
export { useModeContext, ModeProvider } from './ModeContext';

export const MODE = 'live' as const;
export const isLive = true;
