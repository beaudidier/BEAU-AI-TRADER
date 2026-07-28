import { CandlestickSeries, ColorType, createChart, createSeriesMarkers, LineSeries, type UTCTimestamp } from "lightweight-charts";
import { useEffect, useRef, useState } from "react";

import { getTradePlan } from "../services/api";
import type { StockChartData, TradePlan } from "../types/stock";

type TradingChartProps = {
  data: StockChartData;
  plan?: TradePlan | null;
};

const chartHelp = {
  Current: "The latest available price. It is not automatically an entry.",
  Entry: "The planned buy level. Wait for price to reach it before opening a paper trade.",
  Stop: "The planned exit if the setup fails. A gap can cause a larger loss.",
  TP1: "The first rules-based profit target.",
  TP2: "The second, more ambitious rules-based profit target.",
  Signal: "The completed candle on which the setup was identified.",
};

function TradingChart({ data, plan }: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [explanation, setExplanation] = useState(chartHelp.Entry);
  const [loadedPlan, setLoadedPlan] = useState<TradePlan | null>(null);
  const effectivePlan = plan ?? loadedPlan;

  useEffect(() => {
    if (plan) return undefined;
    let active = true;
    void getTradePlan(data.ticker).then((value) => { if (active) setLoadedPlan(value); }).catch(() => { if (active) setLoadedPlan(null); });
    return () => { active = false; };
  }, [data.ticker, plan]);

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
    if (effectivePlan) {
      candleSeries.createPriceLine({ price: effectivePlan.current_price, color: "#f8fafc", lineWidth: 2, lineStyle: 0, axisLabelVisible: true, title: "CURRENT" });
      candleSeries.createPriceLine({ price: effectivePlan.entry, color: "#22d3ee", lineWidth: 3, lineStyle: 0, axisLabelVisible: true, title: "ENTRY ZONE" });
      candleSeries.createPriceLine({ price: effectivePlan.stop_loss, color: "#fb7185", lineWidth: 3, lineStyle: 0, axisLabelVisible: true, title: "STOP ZONE" });
      candleSeries.createPriceLine({ price: effectivePlan.target_1, color: "#4ade80", lineWidth: 2, lineStyle: 2, axisLabelVisible: true, title: "TP1" });
      candleSeries.createPriceLine({ price: effectivePlan.target_2, color: "#a3e635", lineWidth: 2, lineStyle: 2, axisLabelVisible: true, title: "TP2" });
      const signalCandle = data.candles.at(-1);
      if (signalCandle) createSeriesMarkers(candleSeries, [{ time: signalCandle.time as UTCTimestamp, position: "aboveBar", color: "#c084fc", shape: "arrowDown", text: "Signal candle" }]);
    }
    chart.timeScale().fitContent();

    return () => chart.remove();
  }, [data, effectivePlan]);

  return <div><div ref={containerRef} className="h-[28rem] w-full sm:h-[36rem]" />{effectivePlan && <div className="mt-3 rounded-lg border border-slate-800 bg-slate-950/70 p-3"><div className="flex flex-wrap gap-2">{Object.entries(chartHelp).map(([label, help]) => <button key={label} type="button" title={help} onClick={() => setExplanation(help)} className="rounded-full border border-slate-700 px-2.5 py-1 text-xs font-semibold text-slate-200 hover:border-cyan-400 hover:text-cyan-200">{label}</button>)}</div><p aria-live="polite" className="mt-2 text-xs leading-5 text-slate-400">{explanation}</p><p className="mt-1 text-[11px] text-slate-600">Hover or tap a label to explain every chart line.</p></div>}</div>;
}

export default TradingChart;
