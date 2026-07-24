import { type FormEvent, useState } from "react";

import EquityCurveChart from "../components/EquityCurveChart";
import Header from "../components/Header";
import Sidebar, { type AppPage } from "../components/Sidebar";
import TradeCoachPanel from "../components/TradeCoachPanel";
import { runBacktest } from "../services/api";
import { userApi } from "../services/userApi";
import type { BacktestRequest, BacktestResult, BacktestTrade } from "../types/stock";

type BacktestingPageProps = {
  onNavigate: (page: AppPage) => void;
};

const defaultRequest: BacktestRequest = { ticker: "NVDA", start_date: "2024-01-01", end_date: "2025-12-31", minimum_confidence: 65, account_size: 10000, risk_percent: 1 };

const metricLabels: Array<[keyof BacktestResult["summary"], string, string]> = [
  ["total_trades", "Total trades", "number"], ["win_rate", "Win rate", "percent"], ["average_rr", "Average R", "ratio"], ["average_confidence", "Avg. confidence", "number"], ["max_drawdown", "Max drawdown", "percent"], ["profit_factor", "Profit factor", "ratio"], ["expectancy", "Expectancy", "currency"], ["net_profit", "Net profit", "currency"],
];

function BacktestingPage({ onNavigate }: BacktestingPageProps) {
  const [request, setRequest] = useState<BacktestRequest>(defaultRequest);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [selectedTrade, setSelectedTrade] = useState<BacktestTrade | null>(null);

  function updateField(field: keyof BacktestRequest, value: string) {
    const numericFields = ["minimum_confidence", "account_size", "risk_percent"];
    setRequest((current) => ({ ...current, [field]: numericFields.includes(field) ? Number(value) : value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try { setResult(await runBacktest(request)); } catch (loadError) { setError(loadError instanceof Error ? loadError.message : "Unable to run backtest."); } finally { setLoading(false); }
  }

  function exportCsv() {
    if (!result) return;
    const headers = ["ticker", "entry_date", "exit_date", "entry", "exit", "shares", "pnl", "realized_rr", "confidence_score", "exit_reason"];
    const rows = result.trades.map((trade) => headers.map((header) => String(trade[header as keyof typeof trade])).join(","));
    const blob = new Blob([[headers.join(","), ...rows].join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${request.ticker}-backtest.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function saveBacktest() { if (!result) return; try { await userApi.saveBacktest(request.ticker, request, result); setSaveMessage("Backtest saved to your account."); } catch (saveError) { setSaveMessage(saveError instanceof Error ? saveError.message : "Unable to save backtest."); } }

  return <div className="min-h-screen bg-slate-950 font-sans text-slate-100 lg:flex"><Sidebar activePage="backtesting" onNavigate={onNavigate} /><div className="min-w-0 flex-1"><Header eyebrow="Strategy research" title="Backtesting" /><main className="mx-auto max-w-7xl p-5 sm:p-8"><form onSubmit={handleSubmit} className="grid gap-4 rounded-xl border border-slate-800 bg-slate-900/40 p-5 md:grid-cols-3 lg:grid-cols-6"><label className="text-xs font-medium text-slate-400">Ticker<input value={request.ticker} onChange={(event) => updateField("ticker", event.target.value.toUpperCase())} className="mt-2 h-10 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm text-white outline-none focus:border-cyan-400" /></label><label className="text-xs font-medium text-slate-400">Start<input type="date" value={request.start_date} onChange={(event) => updateField("start_date", event.target.value)} className="mt-2 h-10 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm text-white outline-none focus:border-cyan-400" /></label><label className="text-xs font-medium text-slate-400">End<input type="date" value={request.end_date} onChange={(event) => updateField("end_date", event.target.value)} className="mt-2 h-10 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm text-white outline-none focus:border-cyan-400" /></label><label className="text-xs font-medium text-slate-400">Min. confidence<input type="number" min="0" max="100" value={request.minimum_confidence} onChange={(event) => updateField("minimum_confidence", event.target.value)} className="mt-2 h-10 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm text-white outline-none focus:border-cyan-400" /></label><label className="text-xs font-medium text-slate-400">Account size<input type="number" min="1" value={request.account_size} onChange={(event) => updateField("account_size", event.target.value)} className="mt-2 h-10 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm text-white outline-none focus:border-cyan-400" /></label><label className="text-xs font-medium text-slate-400">Risk %<input type="number" min="0.1" max="100" step="0.1" value={request.risk_percent} onChange={(event) => updateField("risk_percent", event.target.value)} className="mt-2 h-10 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm text-white outline-none focus:border-cyan-400" /></label><button type="submit" disabled={loading} className="h-10 rounded-lg bg-cyan-400 px-4 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-70 md:col-span-3 lg:col-span-6">{loading ? "Running simulation…" : "Run backtest"}</button></form>{error && <p className="mt-5 rounded-lg border border-rose-400/20 bg-rose-400/10 p-4 text-sm text-rose-200">{error}</p>}{result && <div className="mt-6 space-y-6"><section className="rounded-xl border border-slate-800 bg-slate-900/40 p-5"><div className="flex items-center justify-between gap-4"><div><h2 className="font-semibold text-white">Equity curve</h2><p className="mt-1 text-sm text-slate-500">${result.summary.starting_equity.toFixed(2)} → ${result.summary.ending_equity.toFixed(2)}</p></div><div className="flex gap-2"><button type="button" onClick={saveBacktest} className="rounded-lg border border-cyan-400/50 px-3 py-2 text-sm font-semibold text-cyan-300">Save run</button><button type="button" onClick={exportCsv} className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-semibold text-slate-200 transition hover:border-cyan-400 hover:text-cyan-300">Export CSV</button></div></div>{saveMessage && <p className="mt-3 text-sm text-slate-400">{saveMessage}</p>}<div className="mt-5">{result.equity_curve.length > 0 ? <EquityCurveChart data={result.equity_curve} /> : <p className="grid h-80 place-items-center text-sm text-slate-500">No equity data for this period.</p>}</div></section><section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{metricLabels.map(([key, label, format]) => { const value = result.summary[key]; const display = format === "currency" ? `$${value.toFixed(2)}` : format === "percent" ? `${value.toFixed(2)}%` : format === "ratio" ? value.toFixed(2) : value.toFixed(0); return <div key={key} className="rounded-xl border border-slate-800 bg-slate-900/40 p-4"><p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p><p className="mt-2 text-xl font-semibold text-white">{display}</p></div>; })}</section><section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/40"><div className="flex items-center justify-between border-b border-slate-800 p-5"><div><h2 className="font-semibold text-white">Trades</h2><p className="mt-1 text-sm text-slate-500">{result.trades.length} completed trades</p></div></div><div className="overflow-x-auto"><table className="w-full min-w-[58rem] text-left text-sm"><thead className="bg-slate-900/70 text-xs uppercase tracking-wider text-slate-500"><tr>{["Entry", "Exit", "Shares", "P&L", "R", "Confidence", "Reason", "Coach"].map((heading) => <th key={heading} className="px-5 py-4 font-medium">{heading}</th>)}</tr></thead><tbody className="divide-y divide-slate-800">{result.trades.map((trade) => <tr key={`${trade.entry_date}-${trade.exit_date}-${trade.shares}`} className="text-slate-300"><td className="px-5 py-4"><p className="font-semibold text-white">${trade.entry.toFixed(2)}</p><p className="text-xs text-slate-500">{trade.entry_date}</p></td><td className="px-5 py-4"><p>${trade.exit.toFixed(2)}</p><p className="text-xs text-slate-500">{trade.exit_date}</p></td><td className="px-5 py-4">{trade.shares}</td><td className={`px-5 py-4 font-semibold ${trade.pnl >= 0 ? "text-emerald-300" : "text-rose-300"}`}>${trade.pnl.toFixed(2)}</td><td className="px-5 py-4">{trade.realized_rr.toFixed(2)}R</td><td className="px-5 py-4">{trade.confidence_score}</td><td className="px-5 py-4">{trade.exit_reason}</td><td className="px-5 py-4"><button type="button" onClick={() => setSelectedTrade(trade)} className="rounded-lg border border-cyan-400/40 px-3 py-1.5 text-xs font-semibold text-cyan-300 transition hover:bg-cyan-400/10">AI Coach</button></td></tr>)}{result.trades.length === 0 && <tr><td colSpan={8} className="px-5 py-12 text-center text-slate-500">No completed trades matched these filters.</td></tr>}</tbody></table></div></section>{selectedTrade && <TradeCoachPanel trade={selectedTrade} />}</div>}</main></div></div>;
}

export default BacktestingPage;
