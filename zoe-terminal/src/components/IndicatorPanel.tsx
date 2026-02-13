import { TrendingUp, TrendingDown, Activity, AlertTriangle, Shield, ShieldOff } from 'lucide-react';
import { cn } from '../lib/utils';

interface MACDData {
  histogram: number;
  histogram_slope: number;
  crossover: number;
  macd_line: number;
  signal_line: number;
}

interface BollingerData {
  percent_b: number;
  squeeze: boolean;
  bandwidth: number;
  upper: number;
  middle: number;
  lower: number;
}

interface ConsensusData {
  result: string;
  confidence: number;
  gates_passed: number;
  gates_total: number;
  blocking_reasons: string[];
  supporting_reasons: string[];
}

interface RegimeData {
  regime: string;
  confidence: number;
  rsi_oversold: number;
  rsi_overbought: number;
}

interface DivergenceData {
  type: string;
  strength: number;
  indicator: string;
  is_reversal: boolean;
  is_bullish: boolean;
}

interface IndicatorPanelProps {
  macd?: MACDData | null;
  bollinger?: BollingerData | null;
  consensus?: ConsensusData | null;
  regime?: RegimeData | null;
  divergences?: DivergenceData[];
  goldenDeathCross?: { type: string; strength: number; bars_since_cross: number } | null;
}

const CONSENSUS_STYLES: Record<string, string> = {
  strong_buy: 'bg-profit/20 text-profit border-profit/30',
  buy: 'bg-profit/10 text-profit/80 border-profit/20',
  neutral: 'bg-yellow-400/10 text-yellow-400 border-yellow-400/20',
  sell: 'bg-loss/10 text-loss/80 border-loss/20',
  strong_sell: 'bg-loss/20 text-loss border-loss/30',
  blocked: 'bg-red-500/20 text-red-400 border-red-500/30',
};

const REGIME_STYLES: Record<string, string> = {
  bull: 'text-profit',
  bear: 'text-loss',
  sideways: 'text-yellow-400',
  high_vol: 'text-orange-400',
};

export default function IndicatorPanel({
  macd,
  bollinger,
  consensus,
  regime,
  divergences,
  goldenDeathCross,
}: IndicatorPanelProps) {
  const hasAnyData = macd || bollinger || consensus || regime || goldenDeathCross || (divergences && divergences.length > 0);

  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-border bg-surface-highlight/20 flex items-center gap-2">
        <Activity className="w-4 h-4 text-text-muted" />
        <h3 className="font-bold text-sm">Advanced Indicators</h3>
      </div>
      <div className="p-6 space-y-4">

      {!hasAnyData && (
        <p className="text-sm text-text-muted/60 italic">Indicator data not yet available. Candles need to accumulate.</p>
      )}

      {/* MACD */}
      {macd && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-text-muted uppercase tracking-wider">MACD</span>
            <div className="flex items-center gap-2">
              {macd.crossover === 1 ? (
                <TrendingUp className="w-3.5 h-3.5 text-profit" />
              ) : macd.crossover === -1 ? (
                <TrendingDown className="w-3.5 h-3.5 text-loss" />
              ) : (
                <Activity className="w-3.5 h-3.5 text-text-muted" />
              )}
              <span className={cn(
                'text-[11px] font-bold tabular-nums',
                macd.histogram > 0 ? 'text-profit' : macd.histogram < 0 ? 'text-loss' : 'text-text-muted'
              )}>
                {macd.histogram > 0 ? '+' : ''}{macd.histogram.toFixed(4)}
              </span>
            </div>
          </div>
          {/* Histogram slope indicator */}
          <div className="flex items-center gap-1.5">
            <span className="text-[9px] text-text-muted">Momentum:</span>
            <span className={cn(
              'text-[9px] font-bold',
              macd.histogram_slope > 0 ? 'text-profit' : macd.histogram_slope < 0 ? 'text-loss' : 'text-text-muted'
            )}>
              {macd.histogram_slope > 0 ? 'Accelerating' : macd.histogram_slope < 0 ? 'Decelerating' : 'Flat'}
            </span>
          </div>
        </div>
      )}

      {/* Bollinger Bands */}
      {bollinger && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-text-muted uppercase tracking-wider">Bollinger</span>
            <span className={cn(
              'text-[11px] font-bold tabular-nums',
              bollinger.percent_b < 0.2 ? 'text-profit' : bollinger.percent_b > 0.8 ? 'text-loss' : 'text-white'
            )}>
              %B {(bollinger.percent_b * 100).toFixed(0)}%
            </span>
          </div>
          {/* BB %B visual bar */}
          <div className="relative h-1.5 bg-background rounded-full overflow-hidden">
            <div
              className={cn(
                'absolute h-full rounded-full transition-all',
                bollinger.percent_b < 0.2 ? 'bg-profit' : bollinger.percent_b > 0.8 ? 'bg-loss' : 'bg-blue-400'
              )}
              style={{ width: `${Math.max(2, Math.min(100, bollinger.percent_b * 100))}%` }}
            />
          </div>
          {bollinger.squeeze && (
            <div className="flex items-center gap-1 mt-1">
              <AlertTriangle className="w-3 h-3 text-orange-400" />
              <span className="text-[9px] font-bold text-orange-400 uppercase tracking-wider">Squeeze Active</span>
            </div>
          )}
        </div>
      )}

      {/* Regime */}
      {regime && (
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold text-text-muted uppercase tracking-wider">Regime</span>
          <span className={cn('text-[10px] font-black uppercase tracking-wider', REGIME_STYLES[regime.regime] ?? 'text-text-muted')}>
            {regime.regime}
          </span>
        </div>
      )}

      {/* Golden / Death Cross */}
      {goldenDeathCross && (
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold text-text-muted uppercase tracking-wider">EMA Cross</span>
          <span className={cn(
            'text-[9px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full border',
            goldenDeathCross.type === 'golden'
              ? 'bg-profit/10 text-profit border-profit/20'
              : 'bg-loss/10 text-loss border-loss/20'
          )}>
            {goldenDeathCross.type === 'golden' ? 'Golden Cross' : 'Death Cross'}
          </span>
        </div>
      )}

      {/* Divergences */}
      {divergences && divergences.length > 0 && (
        <div className="space-y-1">
          <span className="text-[10px] font-bold text-text-muted uppercase tracking-wider">Divergences</span>
          {divergences.slice(0, 2).map((d, i) => (
            <div key={i} className={cn(
              'text-[9px] font-bold uppercase tracking-wider px-2 py-1 rounded border',
              d.is_bullish
                ? 'bg-profit/5 text-profit/80 border-profit/10'
                : 'bg-loss/5 text-loss/80 border-loss/10'
            )}>
              {d.type.replace(/_/g, ' ')} ({d.indicator})
            </div>
          ))}
        </div>
      )}

      {/* Consensus Engine */}
      {consensus && (
        <div className="pt-3 mt-3 border-t border-border/50 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              {consensus.result === 'blocked' ? (
                <ShieldOff className="w-3.5 h-3.5 text-red-400" />
              ) : (
                <Shield className="w-3.5 h-3.5 text-white/60" />
              )}
              <span className="text-[10px] font-black uppercase tracking-[0.2em] text-white">Consensus</span>
            </div>
            <span className={cn(
              'text-[9px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full border',
              CONSENSUS_STYLES[consensus.result] ?? CONSENSUS_STYLES.neutral
            )}>
              {consensus.result.replace(/_/g, ' ')}
            </span>
          </div>

          {/* Gate progress */}
          <div className="flex items-center justify-between text-[9px] text-text-muted">
            <span>Gates Passed</span>
            <span className="font-bold tabular-nums text-white">{consensus.gates_passed}/{consensus.gates_total}</span>
          </div>
          <div className="h-1.5 bg-background rounded-full overflow-hidden">
            <div
              className={cn(
                'h-full rounded-full transition-all',
                consensus.confidence > 0.7 ? 'bg-profit'
                  : consensus.confidence > 0.4 ? 'bg-yellow-400'
                  : 'bg-loss'
              )}
              style={{ width: `${(consensus.gates_passed / consensus.gates_total) * 100}%` }}
            />
          </div>

          {/* Blocking reasons (if any) */}
          {consensus.blocking_reasons.length > 0 && (
            <div className="space-y-0.5 mt-1">
              {consensus.blocking_reasons.slice(0, 2).map((r, i) => (
                <div key={i} className="text-[8px] text-red-400/80 font-medium truncate">
                  {r}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      </div>
    </div>
  );
}
