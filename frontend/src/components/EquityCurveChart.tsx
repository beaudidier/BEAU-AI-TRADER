import { ColorType, createChart, LineSeries } from "lightweight-charts";
import { useEffect, useRef } from "react";

type EquityCurveChartProps = {
  data: Array<{ time: string; value: number }>;
};

function EquityCurveChart({ data }: EquityCurveChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const chart = createChart(container, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "#020617" }, textColor: "#94a3b8" },
      grid: { vertLines: { color: "#172033" }, horzLines: { color: "#172033" } },
      rightPriceScale: { borderColor: "#1e293b" },
      timeScale: { borderColor: "#1e293b" },
    });
    const series = chart.addSeries(LineSeries, { color: "#22d3ee", lineWidth: 2, priceLineVisible: false, lastValueVisible: true });
    series.setData(data.map((point) => ({ time: point.time, value: point.value })));
    chart.timeScale().fitContent();

    return () => chart.remove();
  }, [data]);

  return <div ref={containerRef} className="h-80 w-full sm:h-[26.25rem]" />;
}

export default EquityCurveChart;
