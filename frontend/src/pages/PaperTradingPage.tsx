import { useEffect, useState } from "react";

import Header from "../components/Header";
import Sidebar, { type AppPage } from "../components/Sidebar";
import { userApi } from "../services/userApi";
import type { PaperPortfolio, PaperTrade } from "../types/database";

type PaperTradingPageProps = { onNavigate: (page: AppPage) => void };

function money(value: number) { return `$${value.toFixed(2)}`; }

function PaperTradingPage({ onNavigate }: PaperTradingPageProps) {
  const [portfolio, setPortfolio] = useState<PaperPortfolio | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [closing, setClosing] = useState<string | null>(null);

  async function refresh() {
    setLoading(true); setError(null);
    try { setPortfolio(await userApi.paperPortfolio() as PaperPortfolio); }
    catch (loadError) { setError(loadError instanceof Error ? loadError.message : "Unable to load paper portfolio."); }
    finally { setLoading(false); }
  }

  useEffect(() => { void refresh(); }, []);

  async function closeTrade(trade: PaperTrade) {
    setClosing(trade.id); setError(null);
    try { await userApi.closePaperTrade(trade.id); await refresh(); }
    catch (closeError) { setError(closeError instanceof Error ? closeError.message : "Unable to close paper trade."); }
    finally { setClosing(null); }
  }

  const cards = portfolio ? [["Current balance", money(portfolio.portfolio_balance), "text-white"], ["Today's P/L", money(portfolio.today_pnl), portfolio.today_pnl >= 0 ? "text-emerald-300" : "text-rose-300"], ["Win rate", `${portfolio.win_rate.toFixed(1)}%`, "text-cyan-300"], ["Open positions", String(portfolio.open_positions.length), "text-white"]] : [];
  return <div className="min-h-screen bg-slate-950 font-sans text-slate-100 lg:flex"><Sidebar activePage="paper-trading" onNavigate={onNavigate} /><div className="min-w-0 flex-1"><Header eyebrow="Simulated execution" title="Paper trading" /><main className="mx-auto max-w-7xl p-5 sm:p-8"><div className="flex flex-wrap items-center justify-between gap-4"><p className="text-sm text-slate-400">Practice with simulated funds only. No broker connections or real money.</p><button type="button" onClick={() => void refresh()} disabled={loading} className="rounded-lg border border-cyan-400/40 px-3 py-2 text-sm font-semibold text-cyan-300 transition hover:bg-cyan-400/10 disabled:opacity-60">{loading ? "Refreshing…" : "Refresh portfolio"}</button></div>{error && <p className="mt-5 rounded-lg border border-rose-400/20 bg-rose-400/10 p-4 text-sm text-rose-200">{error}</p>}{loading && !portfolio ? <div className="mt-6 rounded-xl border border-slate-800 bg-slate-900/40 p-6 text-sm text-slate-400">Loading simulated account…</div> : portfolio && <div className="mt-6 space-y-6"><section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{cards.map(([label, value, tone]) => <div key={label} className="rounded-xl border border-slate-800 bg-slate-900/40 p-5"><p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p><p className={`mt-2 text-2xl font-semibold ${tone}`}>{value}</p></div>)}</section><section className="grid gap-3 md:grid-cols-3"><div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5"><p className="text-xs font-medium uppercase tracking-wide text-slate-500">Cash balance</p><p className="mt-2 text-xl font-semibold text-white">{money(portfolio.cash_balance)}</p></div><div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5"><p className="text-xs font-medium uppercase tracking-wide text-slate-500">Unrealized P/L</p><p className={`mt-2 text-xl font-semibold ${portfolio.unrealized_pnl >= 0 ? "text-emerald-300" : "text-rose-300"}`}>{money(portfolio.unrealized_pnl)}</p></div><div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5"><p className="text-xs font-medium uppercase tracking-wide text-slate-500">Realized P/L</p><p className={`mt-2 text-xl font-semibold ${portfolio.realized_pnl >= 0 ? "text-emerald-300" : "text-rose-300"}`}>{money(portfolio.realized_pnl)}</p></div></section><section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/40"><div className="border-b border-slate-800 p-5"><h2 className="font-semibold text-white">Open positions</h2><p className="mt-1 text-sm text-slate-500">Close a position at the latest available market quote.</p></div><div className="overflow-x-auto"><table className="w-full min-w-[48rem] text-left text-sm"><thead className="bg-slate-900/70 text-xs uppercase tracking-wider text-slate-500"><tr>{["Ticker", "Side", "Entry", "Market", "Unrealized", "Plan", "Action"].map((heading) => <th key={heading} className="px-5 py-4 font-medium">{heading}</th>)}</tr></thead><tbody className="divide-y divide-slate-800">{portfolio.open_positions.map((trade) => <tr key={trade.id} className="text-slate-300"><td className="px-5 py-4 font-semibold text-white">{trade.ticker}</td><td className="px-5 py-4">{trade.side}</td><td className="px-5 py-4">{money(trade.entry_price)}</td><td className="px-5 py-4">{money(trade.market_price ?? trade.entry_price)}</td><td className={`px-5 py-4 font-semibold ${(trade.unrealized_pnl ?? 0) >= 0 ? "text-emerald-300" : "text-rose-300"}`}>{money(trade.unrealized_pnl ?? 0)}</td><td className="px-5 py-4 text-xs text-slate-400">Stop {money(trade.stop_loss)} · T1 {money(trade.target_1)}</td><td className="px-5 py-4"><button type="button" onClick={() => void closeTrade(trade)} disabled={closing === trade.id} className="rounded-lg border border-rose-400/40 px-3 py-1.5 text-xs font-semibold text-rose-200 transition hover:bg-rose-400/10 disabled:opacity-60">{closing === trade.id ? "Closing…" : "Close"}</button></td></tr>)}{portfolio.open_positions.length === 0 && <tr><td colSpan={7} className="px-5 py-12 text-center text-slate-500">Open a paper trade from a stock’s trade plan.</td></tr>}</tbody></table></div></section><section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/40"><div className="border-b border-slate-800 p-5"><h2 className="font-semibold text-white">Recent trades</h2></div><div className="divide-y divide-slate-800">{portfolio.recent_trades.map((trade) => <div key={trade.id} className="flex flex-wrap items-center justify-between gap-3 p-5"><div><p className="font-semibold text-white">{trade.ticker} <span className="text-sm font-medium text-slate-500">{trade.side} · {trade.status}</span></p><p className="mt-1 text-xs text-slate-500">{trade.status === "CLOSED" ? "AI Coach review was generated on close." : "Targets and stop are stored with this simulated position."}</p></div><p className={`font-semibold ${(trade.realized_pnl ?? trade.unrealized_pnl ?? 0) >= 0 ? "text-emerald-300" : "text-rose-300"}`}>{money(trade.realized_pnl ?? trade.unrealized_pnl ?? 0)}</p></div>)}{portfolio.recent_trades.length === 0 && <p className="p-5 text-sm text-slate-500">No simulated trades yet.</p>}</div></section></div>}</main></div></div>;
}

export default PaperTradingPage;
