import { CandlestickSeries, ColorType, createChart, LineSeries, type UTCTimestamp } from "lightweight-charts";
import { useEffect, useRef } from "react";

import type { StockChartData } from "../types/stock";

type TradingChartProps = {
  data: StockChartData;
};

function TradingChart({ data }: TradingChartProps) {
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
      crosshair: { vertLine: { color: "#334155" }, horzLine: { color: "#334155" } },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e", downColor: "#f43f5e", borderVisible: false,
      wickUpColor: "#22c55e", wickDownColor: "#f43f5e",
    });
    const ema20Series = chart.addSeries(LineSeries, { color: "#38bdf8", lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    const ema50Series = chart.addSeries(LineSeries, { color: "#f59e0b", lineWidth: 2, priceLineVisible: false, lastValueVisible: false });

    candleSeries.setData(data.candles.map((candle) => ({ ...candle, time: candle.time as UTCTimestamp })));
    ema20Series.setData(data.ema20.map((point) => ({ ...point, time: point.time as UTCTimestamp })));
    ema50Series.setData(data.ema50.map((point) => ({ ...point, time: point.time as UTCTimestamp })));
    candleSeries.createPriceLine({ price: data.support, color: "#22c55e", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "Support" });
    candleSeries.createPriceLine({ price: data.resistance, color: "#f43f5e", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "Resistance" });
    chart.timeScale().fitContent();

    return () => chart.remove();
  }, [data]);

  return <div ref={containerRef} className="h-[28rem] w-full sm:h-[36rem]" />;
}

export default TradingChart;
