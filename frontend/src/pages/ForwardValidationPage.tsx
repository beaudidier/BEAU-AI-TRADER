import { useEffect, useState } from "react";

import ForwardValidationTable from "../components/ForwardValidationTable";
import Header from "../components/Header";
import Sidebar, { type AppPage } from "../components/Sidebar";
import { userApi } from "../services/userApi";
import type { ForwardValidationDashboard } from "../types/database";

type ForwardValidationPageProps = { onNavigate: (page: AppPage) => void };

function metric(value: number | null, suffix = "") {
  return value == null || !Number.isFinite(value) ? "—" : `${value.toFixed(2)}${suffix}`;
}

function ForwardValidationPage({ onNavigate }: ForwardValidationPageProps) {
  const [dashboard, setDashboard] = useState<ForwardValidationDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState<"scan" | "refresh" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    setLoading(true); setError(null);
    try { setDashboard(await userApi.forwardValidationDashboard() as ForwardValidationDashboard); }
    catch { setError("Forward-validation records are unavailable right now. Confirm that the latest database migration has been applied."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);

  async function scan() {
    setAction("scan"); setError(null); setMessage(null);
    try {
      const result = await userApi.scanForwardValidation() as { created_count: number; duplicate_count: number; regime_disallowed_count: number };
      setMessage(`${result.created_count} new immutable signal${result.created_count === 1 ? "" : "s"} recorded. ${result.regime_disallowed_count} stocks were outside the allowed regime; ${result.duplicate_count} were already captured.`);
      await load();
    } catch { setError("The frozen strategy scan could not finish. Please try again after market data is available."); }
    finally { setAction(null); }
  }

  async function refresh() {
    setAction("refresh"); setError(null); setMessage(null);
    try { setDashboard(await userApi.refreshForwardValidation() as ForwardValidationDashboard); setMessage("Forward outcomes were updated from completed daily candles."); }
    catch { setError("Forward outcomes could not be updated right now. No stored signal was changed."); }
    finally { setAction(null); }
  }

  const cards = dashboard ? [
    ["Completed sample", String(dashboard.metrics.total_sample_size)],
    ["Expectancy", metric(dashboard.metrics.expectancy, "R")],
    ["Profit factor", metric(dashboard.metrics.profit_factor)],
    ["Win rate", metric(dashboard.metrics.win_rate, "%")],
    ["Maximum drawdown", metric(dashboard.metrics.maximum_drawdown, "R")],
    ["Double-cost expectancy", metric(dashboard.metrics.double_cost_expectancy, "R")],
  ] : [];
  const approval = dashboard?.metrics.approval;

  return <div className="min-h-screen bg-slate-950 font-sans text-slate-100 lg:flex">
    <Sidebar activePage="forward-validation" onNavigate={onNavigate} />
    <div className="min-w-0 flex-1">
      <Header eyebrow="Paper-only strategy research" title="Forward Validation" />
      <main className="mx-auto max-w-7xl p-5 sm:p-8">
        <section className="rounded-xl border border-amber-400/30 bg-amber-400/10 p-5">
          <p className="text-sm font-semibold text-amber-100">Forward validation only. Not proven for live-money trading.</p>
          <p className="mt-2 text-sm leading-6 text-amber-100/70">No broker connection, real-money execution, or automatic order placement is enabled.</p>
        </section>
        {dashboard && <section className="mt-5 flex flex-col gap-5 rounded-xl border border-slate-800 bg-slate-900/40 p-5 lg:flex-row lg:items-center lg:justify-between">
          <div><div className="flex flex-wrap items-center gap-3"><h2 className="text-xl font-semibold text-white">{dashboard.strategy.name}</h2><span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2.5 py-1 text-xs font-semibold text-cyan-300">{dashboard.strategy.status}</span></div><p className="mt-2 text-sm text-slate-400">{dashboard.strategy.asset_class} · {dashboard.strategy.trading_style} · {dashboard.strategy.direction} · {dashboard.strategy.strategy_version}</p></div>
          <div className="flex flex-wrap gap-3"><button type="button" onClick={() => void scan()} disabled={action !== null} className="rounded-lg bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:opacity-60">{action === "scan" ? "Scanning…" : "Capture today's signals"}</button><button type="button" onClick={() => void refresh()} disabled={action !== null} className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-cyan-400/50 hover:text-white disabled:opacity-60">{action === "refresh" ? "Updating…" : "Update outcomes"}</button></div>
        </section>}
        {error && <p className="mt-5 rounded-lg border border-rose-400/20 bg-rose-400/10 p-4 text-sm text-rose-200">{error}</p>}
        {message && <p className="mt-5 rounded-lg border border-emerald-400/20 bg-emerald-400/10 p-4 text-sm text-emerald-200">{message}</p>}
        {loading && !dashboard ? <div className="mt-5 rounded-xl border border-slate-800 bg-slate-900/40 p-6 text-sm text-slate-400">Loading frozen strategy records…</div> : dashboard && <>
          <section className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{cards.map(([label, value]) => <div key={label} className="rounded-xl border border-slate-800 bg-slate-900/40 p-5"><p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p><p className="mt-2 text-2xl font-semibold text-white">{value}</p></div>)}</section>
          <section className={`mt-5 rounded-xl border p-5 ${approval?.approved ? "border-emerald-400/30 bg-emerald-400/10" : "border-slate-800 bg-slate-900/40"}`}><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold text-white">Minimum approval rules</h2><p className="mt-1 text-sm text-slate-400">{approval?.approved ? "All mechanical paper-validation gates are satisfied." : "The strategy remains unapproved while evidence is incomplete."}</p></div><span className={`rounded-full px-3 py-1 text-xs font-semibold ${approval?.approved ? "bg-emerald-300 text-emerald-950" : "bg-slate-800 text-slate-300"}`}>{approval?.approved ? "MECHANICALLY PASSED" : "VALIDATING"}</span></div><div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-5">{approval && [["100 completed trades", approval.minimum_completed_trades], ["Positive expectancy", approval.positive_expectancy], ["PF above 1", approval.profit_factor_above_one], ["Acceptable drawdown", approval.acceptable_drawdown], ["Positive after double costs", approval.positive_after_double_costs]].map(([label, passed]) => <div key={String(label)} className="rounded-lg bg-slate-950/50 p-3 text-xs text-slate-300"><span className={passed ? "text-emerald-300" : "text-slate-600"}>{passed ? "●" : "○"}</span> {label}</div>)}</div></section>
          <div className="mt-5 space-y-5">
            <ForwardValidationTable title="Active signals" description="Waiting up to three completed daily candles for the frozen EMA20 pullback entry." signals={dashboard.active_signals} emptyMessage="No active frozen-strategy signals." />
            <ForwardValidationTable title="Open paper trades" description="Entered validation positions tracked in R. No real-money orders exist." signals={dashboard.open_paper_trades} emptyMessage="No open forward-validation paper trades." />
            <ForwardValidationTable title="Completed trades" description="Final outcomes include costs, slippage, partial exits, and holding time." signals={dashboard.completed_trades} emptyMessage="No completed forward-validation trades yet." />
            <ForwardValidationTable title="Expired signals" description="Signals whose EMA20 limit was not traded within three completed candles." signals={dashboard.expired_signals} emptyMessage="No expired signals." />
          </div>
        </>}
      </main>
    </div>
  </div>;
}

export default ForwardValidationPage;
