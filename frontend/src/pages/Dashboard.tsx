import { useCallback, useEffect, useState } from "react";

import Header from "../components/Header";
import { BriefingSection } from "../components/BriefingSection";
import ScanButton from "../components/ScanButton";
import Sidebar, { type AppPage } from "../components/Sidebar";
import StockDetailPanel from "../components/StockDetailPanel";
import StockTable from "../components/StockTable";
import { WatchlistManager } from "../components/WatchlistManager";
import { getDailyBriefing, scanMarket } from "../services/api";
import type { DailyBriefing, Stock } from "../types/stock";

type DashboardProps = { onOpenChart: (stock: Stock) => void; onNavigate: (page: AppPage) => void; searchTerm: string; onSearchChange: (value: string) => void };

const retryDelays = [0, 750, 1500];

async function retryRequest<T>(request: () => Promise<T>): Promise<T> {
  let lastError: unknown;
  for (const delay of retryDelays) {
    if (delay) await new Promise((resolve) => window.setTimeout(resolve, delay));
    try { return await request(); } catch (error) { lastError = error; }
  }
  throw lastError;
}

function Dashboard({ onOpenChart, onNavigate, searchTerm, onSearchChange }: DashboardProps) {
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [scannerLoading, setScannerLoading] = useState(true);
  const [scannerError, setScannerError] = useState<string | null>(null);
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null);
  const [briefing, setBriefing] = useState<DailyBriefing | null>(null);
  const [briefingLoading, setBriefingLoading] = useState(true);
  const [briefingError, setBriefingError] = useState<string | null>(null);

  const refreshScanner = useCallback(async () => {
    setScannerLoading(true); setScannerError(null);
    try { setStocks(await retryRequest(scanMarket)); }
    catch { setScannerError("The market scanner is taking longer than expected. Please try again."); }
    finally { setScannerLoading(false); }
  }, []);

  const refreshBriefing = useCallback(async () => {
    setBriefingLoading(true); setBriefingError(null);
    try { setBriefing(await retryRequest(getDailyBriefing)); }
    catch { setBriefingError("Today's market briefing is unavailable right now. Scanner results are still ready to use."); }
    finally { setBriefingLoading(false); }
  }, []);

  const refreshDashboard = useCallback(async () => { await Promise.all([refreshScanner(), refreshBriefing()]); }, [refreshBriefing, refreshScanner]);
  useEffect(() => { void refreshDashboard(); }, [refreshDashboard]);
  const filteredStocks = stocks.filter((stock) => stock.ticker.toLowerCase().includes(searchTerm.toLowerCase()));

  return <div className="min-h-screen bg-slate-950 font-sans text-slate-100 lg:flex"><Sidebar onNavigate={onNavigate} /><div className="min-w-0 flex-1"><Header /><main id="scanner" className="mx-auto max-w-7xl p-5 sm:p-8"><div className="mb-5 flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><p className="text-sm font-medium text-cyan-300">Market scanner</p><h2 className="mt-1 text-2xl font-semibold tracking-tight text-white">Today’s trade candidates</h2><p className="mt-2 text-sm text-slate-400">Review ranked setups first, then open a workspace to validate the plan.</p></div><ScanButton loading={scannerLoading || briefingLoading} onClick={() => void refreshDashboard()} /></div><section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/40 shadow-xl shadow-slate-950/30"><div className="flex flex-col gap-4 border-b border-slate-800 p-5 sm:flex-row sm:items-center sm:justify-between"><div><h3 className="font-semibold text-white">Scanner results</h3><p className="mt-1 text-sm text-slate-500">{scannerLoading && stocks.length === 0 ? "Refreshing market data…" : `${filteredStocks.length} stocks displayed`}</p></div><label className="relative block"><span className="sr-only">Search stocks</span><span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-500" aria-hidden="true">⌕</span><input value={searchTerm} onChange={(event) => onSearchChange(event.target.value)} placeholder="Search ticker" className="h-10 w-full rounded-lg border border-slate-700 bg-slate-950 pl-9 pr-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-400 sm:w-56" /></label></div>{scannerError && <div className="border-b border-amber-400/20 bg-amber-400/10 px-5 py-3 text-sm text-amber-100"><div className="flex flex-wrap items-center justify-between gap-3"><span>{scannerError}</span><button type="button" onClick={() => void refreshScanner()} className="font-semibold text-amber-200 hover:text-white">Try scanner again</button></div></div>}{scannerLoading && stocks.length === 0 ? <div className="grid h-64 place-items-center text-sm text-slate-400"><div className="flex items-center gap-3"><span className="size-4 animate-spin rounded-full border-2 border-cyan-300 border-t-transparent" /> Loading trade candidates…</div></div> : <StockTable stocks={filteredStocks} onOpenChart={onOpenChart} onViewDetails={setSelectedStock} />}</section><section className="mt-6"><div className="mb-3 flex items-end justify-between gap-4"><div><p className="text-sm font-medium text-cyan-300">Daily context</p><h2 className="mt-1 text-xl font-semibold text-white">Market briefing</h2></div>{briefingError && <button type="button" onClick={() => void refreshBriefing()} className="text-sm font-semibold text-cyan-300 hover:text-cyan-200">Retry briefing</button>}</div>{briefingLoading && !briefing && <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 text-sm text-slate-400">Preparing today’s market context…</div>}{briefingError && !briefing && <div className="rounded-xl border border-amber-400/20 bg-amber-400/10 p-5 text-sm text-amber-100">{briefingError}</div>}{briefing && <BriefingSection briefing={briefing} onAnalyze={onOpenChart} />}</section><div className="mt-6"><WatchlistManager onOpenTicker={(ticker) => onOpenChart({ ticker, price: 0, score: 0, recommendation: "WATCH", ema20: 0, ema50: 0, rsi: 0, atr: 0, support: 0, resistance: 0, reasons: [] })} /></div></main></div><StockDetailPanel stock={selectedStock} onClose={() => setSelectedStock(null)} /></div>;
}

export default Dashboard;
