import { useCallback, useEffect, useState } from "react";

import AdviceBadge from "../components/AdviceBadge";
import BeginnerSetup from "../components/BeginnerSetup";
import { BriefingSection } from "../components/BriefingSection";
import Header from "../components/Header";
import PrivateBetaStatusPanel from "../components/PrivateBetaStatusPanel";
import ScanButton from "../components/ScanButton";
import ScoreBadge from "../components/ScoreBadge";
import Sidebar, { type AppPage } from "../components/Sidebar";
import StockDetailPanel from "../components/StockDetailPanel";
import StockTable from "../components/StockTable";
import StrategySelector from "../components/StrategySelector";
import { WatchlistManager } from "../components/WatchlistManager";
import { createScanJob, getDailyBriefing, getScanJob, getScanJobResults, getStrategies, scanMarket } from "../services/api";
import { userApi } from "../services/userApi";
import type { PrivateBetaReadiness } from "../types/database";
import type { DailyBriefing, ScanJob, Stock, TradingStrategy } from "../types/stock";

type DashboardProps = {
  onOpenChart: (stock: Stock) => void;
  onNavigate: (page: AppPage) => void;
  searchTerm: string;
  onSearchChange: (value: string) => void;
};

const retryDelays = [0, 750, 1500];
const universeOptions = [
  { value: "stocks:demo", label: "Demo" },
  { value: "stocks:sp500", label: "S&P 500" },
  { value: "stocks:nasdaq100", label: "Nasdaq 100" },
  { value: "stocks:dow30", label: "Dow 30" },
  { value: "stocks:all_us", label: "All US Stocks" },
  { value: "crypto:top50", label: "Crypto Top 50" },
  { value: "crypto:top100", label: "Crypto Top 100" },
];

function TopOpportunities({
  briefing,
  loading,
  analysedCount,
  lastUpdated,
  onAnalyze,
}: {
  briefing: DailyBriefing | null;
  loading: boolean;
  analysedCount: number;
  lastUpdated: Date | null;
  onAnalyze: (stock: Stock) => void;
}) {
  if (loading && !briefing) {
    return (
      <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
        <p className="text-sm text-slate-400">Finding today’s highest-confidence setups…</p>
      </section>
    );
  }
  if (!briefing) {
    return (
      <section className="rounded-xl border border-amber-400/20 bg-amber-400/10 p-5">
        <p className="text-sm text-amber-100">Top opportunities are temporarily unavailable. Use the scanner below to review current setups.</p>
      </section>
    );
  }

  const opportunities = briefing.opportunities.filter((item) => item.confidence >= 80).slice(0, 5);
  const updateLabel = lastUpdated ? lastUpdated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—";

  return (
    <section className="rounded-xl border border-cyan-400/20 bg-slate-900/40 p-5 shadow-xl shadow-slate-950/30 sm:p-6">
      <div className="flex flex-col gap-3 border-b border-slate-800 pb-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-medium text-cyan-300">Today’s Top Opportunities</p>
          <h2 className="mt-1 text-2xl font-semibold tracking-tight text-white">The strongest setups to review now</h2>
          <p className="mt-2 text-sm text-slate-400">AI analysed {analysedCount} stocks today. {opportunities.length} passed all filters.</p>
        </div>
        <p className="text-xs text-slate-500">Last updated {updateLabel}</p>
      </div>
      {opportunities.length > 0 ? (
        <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          {opportunities.map((item) => (
            <article key={item.ticker} className="flex min-w-0 flex-col rounded-xl border border-slate-800 bg-slate-950/70 p-4 transition hover:border-cyan-400/40">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-lg font-semibold text-white">{item.ticker}</p>
                  <p className="mt-1 text-xs font-medium uppercase tracking-wide text-slate-500">{item.trend || "Trend unavailable"}</p>
                </div>
                <ScoreBadge score={item.confidence} />
              </div>
              <div className="mt-5 space-y-3">
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span className="text-slate-500">Recommendation</span>
                  <AdviceBadge advice={item.recommendation} />
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-500">Risk / reward</span>
                  <span className="font-mono font-semibold text-white">{item.rr.toFixed(2)}R</span>
                </div>
              </div>
              <p className="mt-4 text-xs leading-5 text-slate-400">{item.explanation.summary}</p>
              <button
                type="button"
                onClick={() => onAnalyze({
                  ticker: item.ticker,
                  price: item.price,
                  score: item.confidence,
                  recommendation: item.recommendation,
                  ema20: 0,
                  ema50: 0,
                  rsi: 0,
                  atr: 0,
                  support: 0,
                  resistance: 0,
                  reasons: [],
                })}
                className="mt-5 w-full rounded-lg bg-cyan-400 px-3 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
              >
                Analyze
              </button>
            </article>
          ))}
        </div>
      ) : (
        <div className="mt-5 rounded-lg border border-slate-800 bg-slate-950/50 px-4 py-5 text-sm text-slate-400">
          No opportunities currently meet the 80 confidence threshold. Review the scanner for additional setups.
        </div>
      )}
    </section>
  );
}

async function retryRequest<T>(request: () => Promise<T>): Promise<T> {
  let lastError: unknown;
  for (const delay of retryDelays) {
    if (delay) await new Promise((resolve) => window.setTimeout(resolve, delay));
    try {
      return await request();
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError;
}

function Dashboard({ onOpenChart, onNavigate, searchTerm, onSearchChange }: DashboardProps) {
  const [beginnerMode, setBeginnerMode] = useState(() => window.localStorage.getItem("beau-display-mode") !== "advanced");
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [scannerLoading, setScannerLoading] = useState(true);
  const [scannerError, setScannerError] = useState<string | null>(null);
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null);
  const [briefing, setBriefing] = useState<DailyBriefing | null>(null);
  const [briefingLoading, setBriefingLoading] = useState(true);
  const [briefingError, setBriefingError] = useState<string | null>(null);
  const [briefingUpdatedAt, setBriefingUpdatedAt] = useState<Date | null>(null);
  const [universe, setUniverse] = useState("stocks:demo");
  const [activeScan, setActiveScan] = useState<ScanJob | null>(null);
  const [strategies, setStrategies] = useState<TradingStrategy[]>([]);
  const [selectedStrategyId, setSelectedStrategyId] = useState<TradingStrategy["id"]>("swing_trading");
  const [betaStatus, setBetaStatus] = useState<PrivateBetaReadiness | null>(null);
  const [betaStatusLoading, setBetaStatusLoading] = useState(true);
  const [betaStatusError, setBetaStatusError] = useState<string | null>(null);

  const refreshScanner = useCallback(async () => {
    setScannerLoading(true);
    setScannerError(null);
    try {
      setStocks(await retryRequest(() => scanMarket("swing_trading")));
    } catch {
      setScannerError("The market scanner is taking longer than expected. Please try again.");
    } finally {
      setScannerLoading(false);
    }
  }, []);

  const refreshBriefing = useCallback(async () => {
    setBriefingLoading(true);
    setBriefingError(null);
    try {
      setBriefing(await retryRequest(getDailyBriefing));
      setBriefingUpdatedAt(new Date());
    } catch {
      setBriefingError("Today's market briefing is unavailable right now. Scanner results are still ready to use.");
    } finally {
      setBriefingLoading(false);
    }
  }, []);

  const refreshBetaStatus = useCallback(async () => {
    setBetaStatusLoading(true);
    setBetaStatusError(null);
    try {
      setBetaStatus(
        await retryRequest(
          () => userApi.betaReadiness() as Promise<PrivateBetaReadiness>,
        ),
      );
    } catch {
      setBetaStatusError(
        "System status could not be refreshed. Previous valid information remains available.",
      );
    } finally {
      setBetaStatusLoading(false);
    }
  }, []);

  const startSelectedScan = useCallback(async () => {
    const [market, selectedUniverse] = universe.split(":") as ["stocks" | "crypto", string];
    if (market === "stocks" && selectedUniverse === "demo") {
      setActiveScan(null);
      await refreshScanner();
      return;
    }
    setScannerLoading(true);
    setScannerError(null);
    try {
      const job = await createScanJob(market, selectedUniverse);
      setActiveScan(job);
      if (job.status === "completed") {
        const result = await getScanJobResults(job.job_id);
        setStocks(result.results);
        setScannerLoading(false);
      }
    } catch {
      setScannerError("This market scan could not be started. Please try again.");
      setScannerLoading(false);
    }
  }, [refreshScanner, universe]);

  useEffect(() => {
    if (!activeScan || activeScan.status === "completed") return undefined;
    const timer = window.setTimeout(() => {
      void getScanJob(activeScan.job_id)
        .then(async (job) => {
          setActiveScan(job);
          if (job.status === "completed") {
            const result = await getScanJobResults(job.job_id);
            setStocks(result.results);
            setScannerLoading(false);
          }
        })
        .catch(() => {
          setScannerError("The scan stopped before results were available. Please try again.");
          setScannerLoading(false);
        });
    }, 700);
    return () => window.clearTimeout(timer);
  }, [activeScan]);

  const refreshDashboard = useCallback(async () => {
    await Promise.all([
      refreshScanner(),
      refreshBriefing(),
      refreshBetaStatus(),
    ]);
  }, [refreshBetaStatus, refreshBriefing, refreshScanner]);

  useEffect(() => {
    void refreshDashboard();
    void getStrategies().then(setStrategies).catch(() => setStrategies([]));
  }, [refreshDashboard]);

  const filteredStocks = stocks.filter((stock) => stock.ticker.toLowerCase().includes(searchTerm.toLowerCase()));
  const selectedStrategy = strategies.find((strategy) => strategy.id === selectedStrategyId);
  const strategyIsUsable = selectedStrategyId === "swing_trading"
    && (!selectedStrategy || selectedStrategy.status === "ACTIVE" || selectedStrategy.status === "FORWARD_VALIDATION");

  if (!strategyIsUsable) {
    return (
      <div className="min-h-screen bg-slate-950 font-sans text-slate-100 lg:flex">
        <Sidebar onNavigate={onNavigate} />
        <div className="min-w-0 flex-1">
          <Header eyebrow="Trading desk" title="Choose your trading strategy" />
          <main className="mx-auto max-w-7xl p-5 sm:p-8">
            <StrategySelector strategies={strategies} selectedId={selectedStrategyId} onSelect={setSelectedStrategyId} />
            <section className="mt-5 rounded-xl border border-slate-800 bg-slate-900/40 p-8 text-center">
              <p className="text-lg font-semibold text-white">Coming soon. This engine is not yet validated.</p>
              <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-400">
                Select Swing Trading to use the validated paper-only scanner. This mode will remain unavailable until its own rules pass validation.
              </p>
            </section>
          </main>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 font-sans text-slate-100 lg:flex">
      <Sidebar onNavigate={onNavigate} />
      <div className="min-w-0 flex-1">
        <Header eyebrow="Swing trading · paper-first" title={beginnerMode ? "Your next clear step" : "Trading dashboard"} />
        <main id="scanner" className="mx-auto max-w-7xl p-5 sm:p-8">
          <div data-tour="dashboard-overview" className="mb-5 flex items-center justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900/60 p-3">
            <div><p className="text-sm font-semibold text-white">{beginnerMode ? "Beginner Mode" : "Advanced Mode"}</p><p className="text-xs text-slate-400">{beginnerMode ? "One setup, plain language, risk first." : "Scanner, scores, and technical detail."}</p></div>
            <button type="button" data-tour="mode-switch" onClick={() => setBeginnerMode((current) => { const next = !current; window.localStorage.setItem("beau-display-mode", next ? "beginner" : "advanced"); return next; })} className="min-h-11 rounded-lg border border-cyan-400/30 px-3 py-2 text-sm font-semibold text-cyan-200 hover:bg-cyan-400/10">Switch to {beginnerMode ? "Advanced" : "Beginner"}</button>
          </div>
          {beginnerMode ? <BeginnerSetup /> : <>
          <StrategySelector strategies={strategies} selectedId={selectedStrategyId} onSelect={setSelectedStrategyId} />
          <div className="mt-4">
            <PrivateBetaStatusPanel
              status={betaStatus}
              loading={betaStatusLoading}
              error={betaStatusError}
              onRetry={() => void refreshBetaStatus()}
            />
          </div>
          <div className="mt-4 flex justify-end">
            <ScanButton loading={scannerLoading || briefingLoading} onClick={() => void refreshDashboard()} />
          </div>
          <div className="mt-3">
            <TopOpportunities
              briefing={briefing}
              loading={briefingLoading}
              analysedCount={stocks.length}
              lastUpdated={briefingUpdatedAt}
              onAnalyze={onOpenChart}
            />
          </div>
          <p className="mt-5 rounded-lg border border-cyan-400/20 bg-cyan-400/5 p-3 text-xs leading-5 text-cyan-100">Confidence is a rules-based score, not a guaranteed probability of profit.</p>
          <section className="mt-5 overflow-hidden rounded-xl border border-slate-800 bg-slate-900/40 shadow-xl shadow-slate-950/30">
            <div className="flex flex-col gap-4 border-b border-slate-800 p-5">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="font-semibold text-white">Scanner</h2>
                  <p className="mt-1 text-sm text-slate-500">
                    {activeScan
                      ? `${activeScan.completed_symbols + activeScan.failed_symbols} of ${activeScan.total_symbols} symbols scanned`
                      : scannerLoading && stocks.length === 0
                        ? "Refreshing market data…"
                        : `${filteredStocks.length} stocks displayed`}
                  </p>
                </div>
                <div className="flex flex-wrap gap-3">
                  <select
                    value={universe}
                    onChange={(event) => setUniverse(event.target.value)}
                    disabled={scannerLoading}
                    className="h-10 rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm text-white outline-none focus:border-cyan-400"
                  >
                    {universeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                  <ScanButton loading={scannerLoading} onClick={() => void startSelectedScan()} />
                </div>
              </div>
              <label className="relative block">
                <span className="sr-only">Search stocks</span>
                <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-500" aria-hidden="true">⌕</span>
                <input
                  value={searchTerm}
                  onChange={(event) => onSearchChange(event.target.value)}
                  placeholder="Search ticker"
                  className="h-10 w-full rounded-lg border border-slate-700 bg-slate-950 pl-9 pr-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-400 sm:w-56"
                />
              </label>
            </div>
            {activeScan && activeScan.status !== "completed" && (
              <div className="border-b border-cyan-400/20 bg-cyan-400/5 px-5 py-3 text-sm text-cyan-100">
                Scanning {activeScan.universe}: {activeScan.progress_percentage}% complete · {activeScan.failed_symbols} unavailable
              </div>
            )}
            {scannerError && (
              <div className="border-b border-amber-400/20 bg-amber-400/10 px-5 py-3 text-sm text-amber-100">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <span>{scannerError}</span>
                  <button type="button" onClick={() => void startSelectedScan()} className="font-semibold text-amber-200 hover:text-white">Try scan again</button>
                </div>
              </div>
            )}
            {scannerLoading && stocks.length === 0 ? (
              <div className="grid h-64 place-items-center text-sm text-slate-400">
                <div className="flex items-center gap-3">
                  <span className="size-4 animate-spin rounded-full border-2 border-cyan-300 border-t-transparent" />
                  Loading trade candidates…
                </div>
              </div>
            ) : (
              <StockTable stocks={filteredStocks} onOpenChart={onOpenChart} onViewDetails={setSelectedStock} />
            )}
          </section>
          <section className="mt-5">
            <div className="mb-3 flex items-end justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-cyan-300">Daily context</p>
                <h2 className="mt-1 text-xl font-semibold text-white">Market briefing</h2>
              </div>
              {briefingError && (
                <button type="button" onClick={() => void refreshBriefing()} className="text-sm font-semibold text-cyan-300 hover:text-cyan-200">
                  Retry briefing
                </button>
              )}
            </div>
            {briefingLoading && !briefing && (
              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 text-sm text-slate-400">Preparing today’s market context…</div>
            )}
            {briefingError && !briefing && (
              <div className="rounded-xl border border-amber-400/20 bg-amber-400/10 p-5 text-sm text-amber-100">{briefingError}</div>
            )}
            {briefing && <BriefingSection briefing={briefing} />}
          </section>
          <div className="mt-5">
            <WatchlistManager
              onOpenTicker={(ticker) => onOpenChart({
                ticker,
                price: 0,
                score: 0,
                recommendation: "WATCH",
                ema20: 0,
                ema50: 0,
                rsi: 0,
                atr: 0,
                support: 0,
                resistance: 0,
                reasons: [],
              })}
            />
          </div>
          </>}
        </main>
      </div>
      <StockDetailPanel stock={selectedStock} onClose={() => setSelectedStock(null)} />
    </div>
  );
}

export default Dashboard;
