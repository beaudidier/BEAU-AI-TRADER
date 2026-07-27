import { CandlestickSeries, ColorType, createChart, LineSeries, type UTCTimestamp } from "lightweight-charts";
import { useEffect, useRef } from "react";

import type { DayTradingBars } from "../types/dayTrading";

type DayTradingChartProps = {
  data: DayTradingBars;
};

function DayTradingChart({ data }: DayTradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;
    const chart = createChart(container, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "#020617" }, textColor: "#94a3b8" },
      grid: { vertLines: { color: "#172033" }, horzLines: { color: "#172033" } },
      rightPriceScale: { borderColor: "#1e293b" },
      timeScale: { borderColor: "#1e293b", timeVisible: true, secondsVisible: false },
    });
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#f43f5e",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#f43f5e",
    });
    const vwap = chart.addSeries(LineSeries, {
      color: "#22d3ee",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      title: "VWAP",
    });
    const valid = data.bars
      .filter((bar) => Number.isFinite(new Date(bar.timestamp).getTime()))
      .map((bar) => ({ ...bar, time: Math.floor(new Date(bar.timestamp).getTime() / 1000) as UTCTimestamp }));
    candles.setData(valid.map((bar) => ({
      time: bar.time,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    })));
    vwap.setData(valid.filter((bar) => bar.vwap != null).map((bar) => ({
      time: bar.time,
      value: bar.vwap as number,
    })));
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [data]);

  if (data.bars.length === 0) {
    return <div className="grid h-80 place-items-center rounded-lg bg-slate-950 text-sm text-slate-500">No intraday bars are available yet.</div>;
  }
  return <div ref={containerRef} className="h-80 w-full" aria-label={`${data.ticker} ${data.timeframe} intraday chart`} />;
}

export default DayTradingChart;
