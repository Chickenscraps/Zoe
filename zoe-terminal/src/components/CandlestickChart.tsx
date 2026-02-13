import { useEffect, useRef } from 'react';
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type LineData,
  type Time,
  ColorType,
  CrosshairMode,
  LineStyle,
} from 'lightweight-charts';
import type { CandleData, SRLevel } from '../hooks/useCandleData';

export interface BollingerOverlay {
  upper: number[];
  middle: number[];
  lower: number[];
}

interface CandlestickChartProps {
  candles: CandleData[];
  supportLevels?: SRLevel[];
  resistanceLevels?: SRLevel[];
  bollingerOverlay?: BollingerOverlay | null;
  height?: number;
}

export default function CandlestickChart({
  candles,
  supportLevels = [],
  resistanceLevels = [],
  bollingerOverlay = null,
  height = 400,
}: CandlestickChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const bbUpperRef = useRef<ISeriesApi<'Line'> | null>(null);
  const bbMiddleRef = useRef<ISeriesApi<'Line'> | null>(null);
  const bbLowerRef = useRef<ISeriesApi<'Line'> | null>(null);

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: 'rgba(255, 255, 255, 0.5)',
        fontFamily: "'JetBrains Mono', 'SF Mono', monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.04)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.04)' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: 'rgba(255, 255, 255, 0.15)',
          labelBackgroundColor: '#1a1a2e',
        },
        horzLine: {
          color: 'rgba(255, 255, 255, 0.15)',
          labelBackgroundColor: '#1a1a2e',
        },
      },
      rightPriceScale: {
        borderColor: 'rgba(255, 255, 255, 0.08)',
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: 'rgba(255, 255, 255, 0.08)',
        timeVisible: true,
        secondsVisible: false,
      },
      width: chartContainerRef.current.clientWidth,
      height,
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#2ee59d',
      downColor: '#ff5b6e',
      borderUpColor: '#2ee59d',
      borderDownColor: '#ff5b6e',
      wickUpColor: '#2ee59d',
      wickDownColor: '#ff5b6e',
    });

    // Bollinger Band overlay lines
    const bbUpper = chart.addSeries(LineSeries, {
      color: 'rgba(100, 149, 237, 0.4)',
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    const bbMiddle = chart.addSeries(LineSeries, {
      color: 'rgba(100, 149, 237, 0.25)',
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    const bbLower = chart.addSeries(LineSeries, {
      color: 'rgba(100, 149, 237, 0.4)',
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    bbUpperRef.current = bbUpper;
    bbMiddleRef.current = bbMiddle;
    bbLowerRef.current = bbLower;

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      bbUpperRef.current = null;
      bbMiddleRef.current = null;
      bbLowerRef.current = null;
    };
  }, [height]);

  // Update candle data
  useEffect(() => {
    if (!candleSeriesRef.current || candles.length === 0) return;

    const chartData: CandlestickData<Time>[] = candles.map((c) => ({
      time: c.time as Time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    candleSeriesRef.current.setData(chartData);

    // Auto-fit content
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  }, [candles]);

  // Update Bollinger Band overlay
  useEffect(() => {
    if (!bbUpperRef.current || !bbMiddleRef.current || !bbLowerRef.current) return;
    if (!bollingerOverlay || candles.length === 0) {
      bbUpperRef.current.setData([]);
      bbMiddleRef.current.setData([]);
      bbLowerRef.current.setData([]);
      return;
    }

    const { upper, middle, lower } = bollingerOverlay;
    // BB arrays may be shorter than candles (need period warmup), align to end
    const offset = candles.length - upper.length;

    const toLineData = (values: number[]): LineData<Time>[] =>
      values.map((v, i) => ({
        time: candles[i + offset].time as Time,
        value: v,
      })).filter(d => d.value > 0);

    bbUpperRef.current.setData(toLineData(upper));
    bbMiddleRef.current.setData(toLineData(middle));
    bbLowerRef.current.setData(toLineData(lower));
  }, [candles, bollingerOverlay]);

  // Draw S/R levels as price lines
  useEffect(() => {
    if (!candleSeriesRef.current || candles.length === 0) return;

    // Remove existing price lines (recreate approach)
    // lightweight-charts doesn't have a removeAllPriceLines, so we just update the series

    // Add support lines
    for (const level of supportLevels) {
      candleSeriesRef.current.createPriceLine({
        price: level.price,
        color: 'rgba(46, 229, 157, 0.4)',
        lineWidth: 1,
        lineStyle: 2, // Dashed
        axisLabelVisible: true,
        title: `S ${level.price.toLocaleString()}`,
      });
    }

    // Add resistance lines
    for (const level of resistanceLevels) {
      candleSeriesRef.current.createPriceLine({
        price: level.price,
        color: 'rgba(255, 91, 110, 0.4)',
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: `R ${level.price.toLocaleString()}`,
      });
    }
  }, [candles, supportLevels, resistanceLevels]);

  return (
    <div
      ref={chartContainerRef}
      className="w-full rounded-lg overflow-hidden"
      style={{ height }}
    />
  );
}
