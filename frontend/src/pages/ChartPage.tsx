import { useEffect, useState } from "react";

import Header from "../components/Header";
import Sidebar from "../components/Sidebar";
import TimeframeSelector from "../components/TimeframeSelector";
import TradingChart from "../components/TradingChart";
import { getStockChart } from "../services/api";
import type { Stock, StockChartData, Timeframe } from "../types/stock";

type ChartPageProps = {
  stock: Stock;
  onBack: () => void;
};

function ChartPage({ stock, onBack }: ChartPageProps) {
  const [timeframe, setTimeframe] = useState<Timeframe>("6M");
  const [chartData, setChartData] = useState<StockChartData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [requestId, setRequestId] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function loadChart() {
      setChartData(null);
      setError(null);

      try {
        const data = await getStockChart(stock.ticker, timeframe);

        if (!cancelled) setChartData(data);
      } catch (loadError) {
        if (!cancelled) setError(loadError instanceof Error ? loadError.message : "Unable to load chart data.");
      }
    }

    void loadChart();

    return () => { cancelled = true; };
  }, [requestId, stock.ticker, timeframe]);

  return (
    <div className="min-h-screen bg-slate-950 font-sans text-slate-100 lg:flex">
      <Sidebar />
      <div className="min-w-0 flex-1">
        <Header eyebrow="Technical analysis" title={`${stock.ticker} chart`} />
        <main className="mx-auto max-w-7xl p-5 sm:p-8">
          <button type="button" onClick={onBack} className="mb-6 inline-flex items-center gap-2 text-sm font-medium text-slate-400 transition hover:text-white"><span aria-hidden="true">←</span> Back to scanner</button>
          <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/40 shadow-xl shadow-slate-950/30">
            <div className="flex flex-col gap-5 border-b border-slate-800 p-5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="flex items-baseline gap-3"><h2 className="text-2xl font-semibold tracking-tight text-white">{stock.ticker}</h2><span className="font-mono text-sm text-slate-400">${stock.price.toFixed(2)}</span></div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs font-medium"><span className="text-sky-300">EMA 20</span><span className="text-amber-300">EMA 50</span><span className="text-emerald-300">Support</span><span className="text-rose-300">Resistance</span></div>
              </div>
              <TimeframeSelector value={timeframe} onChange={setTimeframe} />
            </div>
            <div className="p-3 sm:p-5">
              {!chartData && !error && <div className="grid h-[28rem] place-items-center text-sm text-slate-400 sm:h-[36rem]"><div className="flex items-center gap-3"><span className="size-4 animate-spin rounded-full border-2 border-cyan-300 border-t-transparent" aria-hidden="true" /> Loading chart data…</div></div>}
              {error && <div className="grid h-[28rem] place-items-center text-center sm:h-[36rem]"><div><p className="font-medium text-rose-300">Chart unavailable</p><p className="mt-2 text-sm text-slate-500">{error}</p><button type="button" onClick={() => setRequestId((current) => current + 1)} className="mt-5 rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-cyan-400 hover:text-cyan-300">Try again</button></div></div>}
              {chartData && <TradingChart data={chartData} />}
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}

export default ChartPage;
