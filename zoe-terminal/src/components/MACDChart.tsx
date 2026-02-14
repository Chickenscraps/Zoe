import { useEffect, useRef } from 'react';
import {
  createChart,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type HistogramData,
  type LineData,
  type Time,
  ColorType,
  LineStyle,
} from 'lightweight-charts';
import type { CandleData } from '../hooks/useCandleData';

interface MACDChartProps {
  candles: CandleData[];
  fast?: number;
  slow?: number;
  signal?: number;
  height?: number;
}

function computeEMA(values: number[], span: number): number[] {
  if (values.length === 0) return [];
  const k = 2 / (span + 1);
  const result: number[] = [values[0]];
  for (let i = 1; i < values.length; i++) {
    result.push(values[i] * k + result[i - 1] * (1 - k));
  }
  return result;
}

export default function MACDChart({
  candles,
  fast = 8,
  slow = 17,
  signal = 9,
  height = 150,
}: MACDChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const disposedRef = useRef(false);
  const histSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const macdSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const signalSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const seriesInitRef = useRef(false);

  // Create chart once
  useEffect(() => {
    if (!containerRef.current) return;
    disposedRef.current = false;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: 'rgba(255, 255, 255, 0.4)',
        fontFamily: "'JetBrains Mono', 'SF Mono', monospace",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.03)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.03)' },
      },
      rightPriceScale: {
        borderColor: 'rgba(255, 255, 255, 0.06)',
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: 'rgba(255, 255, 255, 0.06)',
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        vertLine: { color: 'rgba(255, 255, 255, 0.1)', labelBackgroundColor: '#1a1a2e' },
        horzLine: { color: 'rgba(255, 255, 255, 0.1)', labelBackgroundColor: '#1a1a2e' },
      },
      width: containerRef.current.clientWidth,
      height,
    });

    // Pre-create all three series so we can just setData later
    const histSeries = chart.addSeries(HistogramSeries, {
      priceLineVisible: false,
      lastValueVisible: false,
    });

    const macdSeries = chart.addSeries(LineSeries, {
      color: 'rgba(100, 149, 237, 0.9)',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    const signalSeries = chart.addSeries(LineSeries, {
      color: 'rgba(255, 165, 0, 0.7)',
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    chartRef.current = chart;
    histSeriesRef.current = histSeries;
    macdSeriesRef.current = macdSeries;
    signalSeriesRef.current = signalSeries;
    seriesInitRef.current = true;

    const handleResize = () => {
      if (containerRef.current && !disposedRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      disposedRef.current = true;
      chart.remove();
      chartRef.current = null;
      histSeriesRef.current = null;
      macdSeriesRef.current = null;
      signalSeriesRef.current = null;
      seriesInitRef.current = false;
    };
  }, [height]);

  // Update MACD data when candles change — just setData, no chart recreation
  useEffect(() => {
    if (disposedRef.current || !seriesInitRef.current) return;
    if (!chartRef.current || !histSeriesRef.current || !macdSeriesRef.current || !signalSeriesRef.current) return;
    if (candles.length < slow + signal) {
      // Not enough data — clear series
      histSeriesRef.current.setData([]);
      macdSeriesRef.current.setData([]);
      signalSeriesRef.current.setData([]);
      return;
    }

    // Compute MACD
    const closes = candles.map(c => c.close);
    const fastEma = computeEMA(closes, fast);
    const slowEma = computeEMA(closes, slow);

    const macdLine = fastEma.map((v, i) => v - slowEma[i]);
    const signalLine = computeEMA(macdLine, signal);
    const histogram = macdLine.map((v, i) => v - signalLine[i]);

    // Update histogram
    const histData: HistogramData<Time>[] = histogram.map((h, i) => ({
      time: candles[i].time as Time,
      value: h,
      color: h >= 0
        ? (i > 0 && h > histogram[i - 1] ? 'rgba(46, 229, 157, 0.8)' : 'rgba(46, 229, 157, 0.35)')
        : (i > 0 && h < histogram[i - 1] ? 'rgba(255, 91, 110, 0.8)' : 'rgba(255, 91, 110, 0.35)'),
    }));
    histSeriesRef.current.setData(histData);

    // Update MACD line
    const macdData: LineData<Time>[] = macdLine.map((v, i) => ({
      time: candles[i].time as Time,
      value: v,
    }));
    macdSeriesRef.current.setData(macdData);

    // Update signal line
    const sigData: LineData<Time>[] = signalLine.map((v, i) => ({
      time: candles[i].time as Time,
      value: v,
    }));
    signalSeriesRef.current.setData(sigData);

    chartRef.current.timeScale().fitContent();
  }, [candles, fast, slow, signal]);

  return (
    <div
      ref={containerRef}
      className="w-full overflow-hidden"
      style={{ height }}
    />
  );
}
