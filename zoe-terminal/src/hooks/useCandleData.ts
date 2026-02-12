import { useEffect, useState, useCallback } from 'react';
import { supabase } from '../lib/supabaseClient';
import { MODE } from '../lib/mode';
import type { Database } from '../lib/types';

type CandleRow = Database['public']['Tables']['crypto_candles']['Row'];
type CandidateScan = Database['public']['Tables']['candidate_scans']['Row'];

export interface CandleData {
  time: number; // Unix timestamp
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface PatternInfo {
  name: string;
  direction: 'bullish' | 'bearish' | 'neutral';
  strength: number;
  candle_index: number;
}

export interface MTFDetail {
  timeframe: string;
  trend: 'bullish' | 'bearish' | 'neutral';
  strength: number;
  rsi: number | null;
  momentum: number | null;
}

export interface SRLevel {
  price: number;
  type: 'support' | 'resistance';
  strength: number;
}

export interface ChartAnalysis {
  patterns: PatternInfo[];
  mtfAlignment: number | null;
  mtfDominantTrend: string | null;
  mtfDetails: MTFDetail[];
  supportLevels: SRLevel[];
  resistanceLevels: SRLevel[];
}

export function useCandleData(symbol: string, timeframe: string = '1h') {
  const [candles, setCandles] = useState<CandleData[]>([]);
  const [loading, setLoading] = useState(true);
  const [analysis, setAnalysis] = useState<ChartAnalysis>({
    patterns: [],
    mtfAlignment: null,
    mtfDominantTrend: null,
    mtfDetails: [],
    supportLevels: [],
    resistanceLevels: [],
  });

  const fetchCandles = useCallback(async () => {
    try {
      // Fetch candles from Supabase
      const { data, error } = await supabase
        .from('crypto_candles')
        .select('*')
        .eq('symbol', symbol)
        .eq('timeframe', timeframe)
        .eq('mode', MODE)
        .order('open_time', { ascending: true })
        .limit(100);

      if (error) throw error;

      if (data && data.length > 0) {
        const mapped: CandleData[] = data.map((c: CandleRow) => ({
          time: c.open_time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
          volume: c.volume,
        }));
        setCandles(mapped);
      }

      // Fetch chart analysis data from latest candidate scan
      const { data: scanData } = await supabase
        .from('candidate_scans')
        .select('info')
        .eq('symbol', symbol)
        .eq('mode', MODE)
        .order('created_at', { ascending: false })
        .limit(1)
        .maybeSingle();

      if (scanData?.info) {
        const info = scanData.info as any;
        setAnalysis({
          patterns: info.patterns ?? [],
          mtfAlignment: info.mtf_alignment ?? null,
          mtfDominantTrend: info.mtf_dominant_trend ?? null,
          mtfDetails: info.mtf_details ?? [],
          supportLevels: info.support_levels ?? [],
          resistanceLevels: info.resistance_levels ?? [],
        });
      }
    } catch (err) {
      console.error('Error fetching candle data:', err);
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe]);

  useEffect(() => {
    setLoading(true);
    fetchCandles();
    const interval = setInterval(fetchCandles, 60000); // Refresh every 60s
    return () => clearInterval(interval);
  }, [fetchCandles]);

  return { candles, loading, analysis, refetch: fetchCandles };
}
