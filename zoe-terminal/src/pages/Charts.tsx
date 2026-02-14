import { useState, useEffect, useMemo } from 'react';
import { TrendingUp, TrendingDown, Minus, BarChart3, Layers, Shield, Activity } from 'lucide-react';
import CandlestickChart from '../components/CandlestickChart';
import type { BollingerOverlay } from '../components/CandlestickChart';
import IndicatorPanel from '../components/IndicatorPanel';
import MACDChart from '../components/MACDChart';
import { useCandleData, type PatternInfo, type MTFDetail } from '../hooks/useCandleData';
import { supabase } from '../lib/supabaseClient';

import { cn } from '../lib/utils';

const SYMBOLS = [
  'BTC-USD', 'ETH-USD', 'DOGE-USD', 'SOL-USD', 'SHIB-USD',
  'AVAX-USD', 'LINK-USD', 'XLM-USD', 'LTC-USD', 'UNI-USD',
];

const TIMEFRAMES = ['15m', '1h', '4h'] as const;

export default function Charts() {
  const [selectedSymbol, setSelectedSymbol] = useState('BTC-USD');
  const [selectedTimeframe, setSelectedTimeframe] = useState<string>('1h');
  const [symbolPrices, setSymbolPrices] = useState<Record<string, number>>({});

  const { candles, loading, analysis } = useCandleData(selectedSymbol, selectedTimeframe);
  const chartHeight = typeof window !== 'undefined' && window.innerWidth < 640 ? 280 : 400;

  // Compute BB overlay from candle closes (client-side for chart rendering)
  const bollingerOverlay = useMemo<BollingerOverlay | null>(() => {
    if (candles.length < 20) return null;
    const closes = candles.map(c => c.close);
    const period = 20;
    const stdMult = 2.0;
    const upper: number[] = [];
    const middle: number[] = [];
    const lower: number[] = [];

    for (let i = period - 1; i < closes.length; i++) {
      const slice = closes.slice(i - period + 1, i + 1);
      const mean = slice.reduce((a, b) => a + b, 0) / period;
      const variance = slice.reduce((a, b) => a + (b - mean) ** 2, 0) / period;
      const std = Math.sqrt(variance);
      middle.push(mean);
      upper.push(mean + stdMult * std);
      lower.push(mean - stdMult * std);
    }

    return { upper, middle, lower };
  }, [candles]);

  // Fetch latest prices for symbol selector
  useEffect(() => {
    async function fetchPrices() {
      try {
        const { data } = await supabase
          .from('candidate_scans')
          .select('symbol, info')
          .order('created_at', { ascending: false })
          .limit(10);

        if (data) {
          const prices: Record<string, number> = {};
          for (const row of data) {
            const info = row.info as any;
            if (info?.mid && !prices[row.symbol]) {
              prices[row.symbol] = info.mid;
            }
          }
          setSymbolPrices(prices);
        }
      } catch { /* non-critical */ }
    }
    fetchPrices();
  }, []);

  const trendIcon = (trend: string) => {
    if (trend === 'bullish') return <TrendingUp className="w-4 h-4 text-profit" />;
    if (trend === 'bearish') return <TrendingDown className="w-4 h-4 text-loss" />;
    return <Minus className="w-4 h-4 text-text-muted" />;
  };

  const trendColor = (trend: string) => {
    if (trend === 'bullish') return 'text-profit';
    if (trend === 'bearish') return 'text-loss';
    return 'text-text-muted';
  };

  const alignmentColor = (score: number | null) => {
    if (score === null) return 'text-text-muted';
    if (score > 0.3) return 'text-profit';
    if (score < -0.3) return 'text-loss';
    return 'text-yellow-400';
  };

  const patternColor = (dir: string) => {
    if (dir === 'bullish') return 'bg-profit/10 text-profit border-profit/20';
    if (dir === 'bearish') return 'bg-loss/10 text-loss border-loss/20';
    return 'bg-yellow-400/10 text-yellow-400 border-yellow-400/20';
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-2 border-b border-earth-700/10 pb-4 sm:pb-8">
        <div>
          <h2 className="font-pixel text-[0.65rem] uppercase tracking-[0.08em] text-earth-700">Chart Analysis</h2>
          <p className="text-xs sm:text-sm text-text-muted mt-1 font-medium tracking-tight">
            Candlestick patterns, MTF trends &amp; S/R
          </p>
        </div>
      </div>

      {/* Controls Row */}
      <div className="flex flex-col sm:flex-row flex-wrap gap-3 sm:gap-4 items-start sm:items-center">
        {/* Symbol Selector */}
        <div className="grid grid-cols-5 sm:flex gap-1.5 w-full sm:w-auto">
          {SYMBOLS.map((sym) => (
            <button
              key={sym}
              onClick={() => setSelectedSymbol(sym)}
              className={cn(
                'px-3 py-1.5 rounded-[4px] text-xs font-bold tracking-tight transition-all',
                selectedSymbol === sym
                  ? 'bg-earth-700 text-cream-100'
                  : 'bg-cream-100/60 text-text-muted border border-earth-700/10 hover:text-earth-700 hover:bg-paper-100'
              )}
            >
              {sym.replace('-USD', '')}
            </button>
          ))}
        </div>

        {/* Divider */}
        <div className="h-6 w-px bg-earth-700/10 hidden sm:block" />

        {/* Timeframe Selector */}
        <div className="flex gap-1">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => setSelectedTimeframe(tf)}
              className={cn(
                'px-4 py-1.5 rounded-[4px] text-xs font-black uppercase tracking-widest transition-all',
                selectedTimeframe === tf
                  ? 'bg-sakura-500/15 text-sakura-700 border-2 border-sakura-500/30'
                  : 'bg-cream-100/60 text-text-muted hover:text-earth-700 border-2 border-earth-700/10'
              )}
            >
              {tf}
            </button>
          ))}
        </div>

        {/* MTF Alignment Badge */}
        {analysis.mtfAlignment !== null && (
          <div className={cn(
            'flex items-center gap-2 px-4 py-1.5 rounded-[4px] border text-xs font-bold',
            analysis.mtfAlignment > 0.3
              ? 'bg-profit/10 border-profit/20 text-profit'
              : analysis.mtfAlignment < -0.3
                ? 'bg-loss/10 border-loss/20 text-loss'
                : 'bg-yellow-400/10 border-yellow-400/20 text-yellow-400'
          )}>
            {trendIcon(analysis.mtfDominantTrend ?? 'neutral')}
            <span>MTF: {(analysis.mtfAlignment > 0 ? '+' : '')}{analysis.mtfAlignment.toFixed(2)}</span>
            <span className="uppercase tracking-widest text-[9px]">{analysis.mtfDominantTrend}</span>
          </div>
        )}
      </div>

      {/* Main Chart */}
      <div className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] overflow-hidden">
        <div className="px-6 py-4 border-b border-earth-700/10 bg-cream-100/40 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BarChart3 className="w-4 h-4 text-text-muted" />
            <h3 className="font-black text-sm tracking-tight">{selectedSymbol}</h3>
            <span className="text-[10px] text-text-muted font-bold uppercase tracking-widest">{selectedTimeframe}</span>
            {symbolPrices[selectedSymbol] && (
              <span className="text-sm font-mono text-earth-700">${symbolPrices[selectedSymbol].toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
            )}
          </div>
          <span className="text-[10px] text-text-muted font-medium">
            {candles.length} candles
          </span>
        </div>

        <div className="p-2">
          {loading ? (
            <div className="flex items-center justify-center text-text-muted animate-pulse" style={{ height: chartHeight }}>
              Loading chart data...
            </div>
          ) : candles.length > 0 ? (
            <CandlestickChart
              candles={candles}
              supportLevels={analysis.supportLevels}
              resistanceLevels={analysis.resistanceLevels}
              bollingerOverlay={bollingerOverlay}
              height={chartHeight}
            />
          ) : (
            <div className="flex flex-col items-center justify-center text-text-muted gap-3" style={{ height: chartHeight }}>
              <BarChart3 className="w-10 h-10 text-earth-700/20 opacity-50" />
              <p className="text-sm">No candle data yet for {selectedSymbol} ({selectedTimeframe})</p>
              <p className="text-xs text-text-muted/60">Candles will appear as the trader collects price data</p>
            </div>
          )}
        </div>
      </div>

      {/* MACD Sub-Chart */}
      {candles.length >= 26 && (
        <div className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] overflow-hidden">
          <div className="px-6 py-3 border-b border-earth-700/10 bg-cream-100/40 flex items-center gap-2">
            <Activity className="w-3.5 h-3.5 text-text-muted" />
            <h3 className="font-bold text-xs tracking-tight">MACD (8, 17, 9)</h3>
            {analysis.macd && (
              <span className={cn(
                'text-[9px] font-black uppercase tracking-wider ml-auto',
                analysis.macd.histogram > 0 ? 'text-profit' : analysis.macd.histogram < 0 ? 'text-loss' : 'text-text-muted'
              )}>
                Hist: {analysis.macd.histogram > 0 ? '+' : ''}{analysis.macd.histogram.toFixed(4)}
                {analysis.macd.histogram_slope > 0 ? ' ▲' : analysis.macd.histogram_slope < 0 ? ' ▼' : ''}
              </span>
            )}
          </div>
          <div className="p-2">
            <MACDChart candles={candles} fast={8} slow={17} signal={9} height={150} />
          </div>
        </div>
      )}

      {/* Bottom Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Advanced Indicators */}
        <IndicatorPanel
          macd={analysis.macd}
          bollinger={analysis.bollinger}
          consensus={analysis.consensus}
          regime={analysis.regime}
          divergences={analysis.divergences}
          goldenDeathCross={analysis.goldenDeathCross}
        />

        {/* Active Patterns */}
        <div className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] overflow-hidden">
          <div className="px-6 py-4 border-b border-earth-700/10 bg-cream-100/40 flex items-center gap-2">
            <Layers className="w-4 h-4 text-text-muted" />
            <h3 className="font-bold text-sm">Active Patterns</h3>
          </div>
          <div className="p-6">
            {analysis.patterns.length > 0 ? (
              <div className="space-y-2">
                {analysis.patterns.map((p: PatternInfo, i: number) => (
                  <div key={`${p.name}-${i}`} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {trendIcon(p.direction)}
                      <span className={cn(
                        'text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full border',
                        patternColor(p.direction)
                      )}>
                        {p.name.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-cream-100/80 rounded-full overflow-hidden">
                        <div
                          className={cn('h-full rounded-full', p.direction === 'bullish' ? 'bg-profit' : p.direction === 'bearish' ? 'bg-loss' : 'bg-yellow-400')}
                          style={{ width: `${p.strength * 100}%` }}
                        />
                      </div>
                      <span className="text-[10px] text-text-muted font-mono">{(p.strength * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-text-muted/60 italic">No patterns detected on current timeframe</p>
            )}
          </div>
        </div>

        {/* Multi-Timeframe Summary */}
        <div className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] overflow-hidden">
          <div className="px-6 py-4 border-b border-earth-700/10 bg-cream-100/40 flex items-center gap-2">
            <Shield className="w-4 h-4 text-text-muted" />
            <h3 className="font-bold text-sm">Multi-Timeframe Summary</h3>
          </div>
          <div className="p-6">
            {analysis.mtfDetails.length > 0 ? (
              <div className="space-y-3">
                {analysis.mtfDetails.map((tf: MTFDetail) => (
                  <div key={tf.timeframe} className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-black uppercase tracking-widest text-text-muted w-8">{tf.timeframe}</span>
                      {trendIcon(tf.trend)}
                      <span className={cn('text-xs font-bold capitalize', trendColor(tf.trend))}>
                        {tf.trend}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-[11px] font-mono">
                      {tf.rsi !== null && (
                        <span className={cn(
                          tf.rsi > 70 ? 'text-loss' : tf.rsi < 30 ? 'text-profit' : 'text-text-secondary'
                        )}>
                          RSI {tf.rsi.toFixed(0)}
                        </span>
                      )}
                      {tf.momentum !== null && (
                        <span className={cn(
                          tf.momentum > 0 ? 'text-profit' : tf.momentum < 0 ? 'text-loss' : 'text-text-muted'
                        )}>
                          {tf.momentum > 0 ? '+' : ''}{tf.momentum.toFixed(2)}%
                        </span>
                      )}
                      <div className="w-12 h-1.5 bg-cream-100/80 rounded-full overflow-hidden">
                        <div
                          className={cn('h-full rounded-full', trendColor(tf.trend).replace('text-', 'bg-'))}
                          style={{ width: `${tf.strength * 100}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ))}

                {/* Overall alignment */}
                {analysis.mtfAlignment !== null && (
                  <div className="pt-3 mt-3 border-t border-earth-700/10 flex items-center justify-between">
                    <span className="text-xs font-bold text-text-muted uppercase tracking-widest">Alignment</span>
                    <span className={cn('text-lg font-black tabular-nums', alignmentColor(analysis.mtfAlignment))}>
                      {analysis.mtfAlignment > 0 ? '+' : ''}{analysis.mtfAlignment.toFixed(3)}
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-text-muted/60 italic">Multi-timeframe data not yet available. Candles need to accumulate.</p>
            )}
          </div>
        </div>
      </div>

      {/* Support/Resistance Levels */}
      {(analysis.supportLevels.length > 0 || analysis.resistanceLevels.length > 0) && (
        <div className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] p-6">
          <h3 className="font-bold text-sm mb-4 text-text-secondary">Support &amp; Resistance Levels</h3>
          <div className="flex flex-wrap gap-3">
            {analysis.supportLevels.map((l, i) => (
              <span key={`s-${i}`} className="px-3 py-1.5 bg-profit/10 text-profit border border-profit/20 rounded-[4px] text-xs font-mono font-bold">
                S: ${l.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                <span className="text-profit/50 ml-1">({l.strength}x)</span>
              </span>
            ))}
            {analysis.resistanceLevels.map((l, i) => (
              <span key={`r-${i}`} className="px-3 py-1.5 bg-loss/10 text-loss border border-loss/20 rounded-[4px] text-xs font-mono font-bold">
                R: ${l.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                <span className="text-loss/50 ml-1">({l.strength}x)</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
