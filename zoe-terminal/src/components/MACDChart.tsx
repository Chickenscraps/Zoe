import { useEffect, useRef } from 'react';
import {
  createChart,
  type IChartApi,
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

  useEffect(() => {
    if (!containerRef.current) return;

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

    chartRef.current = chart;

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartRef.current = null;
    };
  }, [height]);

  // Compute and render MACD data
  useEffect(() => {
    if (!chartRef.current || candles.length < slow + signal) return;
    const chart = chartRef.current;

    // Clear existing series by removing chart and recreating is expensive,
    // instead we'll just set data on existing series. But since series refs
    // aren't persistent across candle changes, we recreate each time.
    // lightweight-charts doesn't support removing series, so we create fresh.

    // Remove old chart and recreate
    const container = containerRef.current;
    if (!container) return;

    chart.remove();

    const newChart = createChart(container, {
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
      width: container.clientWidth,
      height,
    });

    chartRef.current = newChart;

    // Compute MACD
    const closes = candles.map(c => c.close);
    const fastEma = computeEMA(closes, fast);
    const slowEma = computeEMA(closes, slow);

    const macdLine = fastEma.map((v, i) => v - slowEma[i]);
    const signalLine = computeEMA(macdLine, signal);
    const histogram = macdLine.map((v, i) => v - signalLine[i]);

    // MACD histogram as colored bars
    const histSeries = (newChart as any).addHistogramSeries({
      priceLineVisible: false,
      lastValueVisible: false,
    });

    const histData: HistogramData<Time>[] = histogram.map((h, i) => ({
      time: candles[i].time as Time,
      value: h,
      color: h >= 0
        ? (i > 0 && h > histogram[i - 1] ? 'rgba(46, 229, 157, 0.8)' : 'rgba(46, 229, 157, 0.35)')
        : (i > 0 && h < histogram[i - 1] ? 'rgba(255, 91, 110, 0.8)' : 'rgba(255, 91, 110, 0.35)'),
    }));
    histSeries.setData(histData);

    // MACD line
    const macdSeries = (newChart as any).addLineSeries({
      color: 'rgba(100, 149, 237, 0.9)',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    const macdData: LineData<Time>[] = macdLine.map((v, i) => ({
      time: candles[i].time as Time,
      value: v,
    }));
    macdSeries.setData(macdData);

    // Signal line
    const signalSeries = (newChart as any).addLineSeries({
      color: 'rgba(255, 165, 0, 0.7)',
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    const sigData: LineData<Time>[] = signalLine.map((v, i) => ({
      time: candles[i].time as Time,
      value: v,
    }));
    signalSeries.setData(sigData);

    newChart.timeScale().fitContent();

    const handleResize = () => {
      if (container) {
        newChart.applyOptions({ width: container.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [candles, fast, slow, signal, height]);

  return (
    <div
      ref={containerRef}
      className="w-full rounded-lg overflow-hidden"
      style={{ height }}
    />
  );
}
