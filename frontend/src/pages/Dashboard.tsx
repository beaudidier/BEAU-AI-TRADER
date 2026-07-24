import { useEffect, useState } from "react";

import Header from "../components/Header";
import { BriefingSection } from "../components/BriefingSection";
import ScanButton from "../components/ScanButton";
import Sidebar, { type AppPage } from "../components/Sidebar";
import StockDetailPanel from "../components/StockDetailPanel";
import StockTable from "../components/StockTable";
import { WatchlistManager } from "../components/WatchlistManager";
import { getDailyBriefing, scanMarket } from "../services/api";
import type { DailyBriefing, Stock } from "../types/stock";

type DashboardProps = {
  onOpenChart: (stock: Stock) => void;
  onNavigate: (page: AppPage) => void;
};

function Dashboard({ onOpenChart, onNavigate }: DashboardProps) {
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null);
  const [briefing, setBriefing] = useState<DailyBriefing | null>(null);
  const [briefingError, setBriefingError] = useState<string | null>(null);

  async function handleScanMarket() {
    setLoading(true);
    setBriefingError(null);
    try {
      const [results, dailyBriefing] = await Promise.all([scanMarket(), getDailyBriefing()]);
      setStocks(results); setBriefing(dailyBriefing);
    } catch (error) { setBriefingError(error instanceof Error ? error.message : "Unable to refresh dashboard."); }
    finally { setLoading(false); }
  }

  useEffect(() => {
    void handleScanMarket();
  }, []);

  const filteredStocks = stocks.filter((stock) => stock.ticker.toLowerCase().includes(searchTerm.toLowerCase()));

  return (
    <div className="min-h-screen bg-slate-950 font-sans text-slate-100 lg:flex">
      <Sidebar onNavigate={onNavigate} />
      <div className="min-w-0 flex-1">
        <Header />
        <main id="scanner" className="mx-auto max-w-7xl p-5 sm:p-8">
          <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <p className="text-sm font-medium text-cyan-300">BEAU AI Daily Briefing</p>
              <h2 className="mt-1 text-2xl font-semibold tracking-tight text-white">Your market intelligence, refreshed daily.</h2>
              <p className="mt-2 text-sm text-slate-400">Review opportunities, watchlist signals, and market conditions in one place.</p>
            </div>
            <ScanButton loading={loading} onClick={handleScanMarket} />
          </div>
          {briefingError && <p className="mb-6 rounded-lg border border-rose-400/20 bg-rose-400/10 p-4 text-sm text-rose-200">{briefingError}</p>}
          {!briefing && !briefingError && <div className="grid h-60 place-items-center rounded-xl border border-slate-800 bg-slate-900/40 text-sm text-slate-400">Loading AI daily briefing…</div>}
          {briefing && <div className="mb-8"><BriefingSection briefing={briefing} onAnalyze={onOpenChart} /></div>}
          <div className="mb-4"><h2 className="text-xl font-semibold text-white">Scanner workspace</h2><p className="mt-1 text-sm text-slate-500">The full scanner remains available below the daily briefing.</p></div>
          <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/40 shadow-xl shadow-slate-950/30">
            <div className="flex flex-col gap-4 border-b border-slate-800 p-5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="font-semibold text-white">Scanner results</h3>
                <p className="mt-1 text-sm text-slate-500">{filteredStocks.length} stocks displayed</p>
              </div>
              <label className="relative block">
                <span className="sr-only">Search stocks</span>
                <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-500" aria-hidden="true">⌕</span>
                <input value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Search ticker" className="h-10 w-full rounded-lg border border-slate-700 bg-slate-950 pl-9 pr-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-400 sm:w-56" />
              </label>
            </div>
            <StockTable stocks={filteredStocks} onOpenChart={onOpenChart} onViewDetails={setSelectedStock} />
          </section>
          <div className="mt-6"><WatchlistManager /></div>
        </main>
      </div>
      <StockDetailPanel stock={selectedStock} onClose={() => setSelectedStock(null)} />
    </div>
  );
}

export default Dashboard;
