import { useCallback, useEffect, useState } from "react";

import ForwardValidationTable from "../components/ForwardValidationTable";
import Header from "../components/Header";
import Sidebar, { type AppPage } from "../components/Sidebar";
import { userApi } from "../services/userApi";
import type { ForwardValidationDashboard, ForwardValidationRun } from "../types/database";

type ForwardValidationPageProps = { onNavigate: (page: AppPage) => void };

function metric(value: number | null, suffix = "") {
  return value == null || !Number.isFinite(value) ? "—" : `${value.toFixed(2)}${suffix}`;
}

function dateTime(value?: string | null) {
  if (!value) return "Not available yet";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "Not available yet" : parsed.toLocaleString();
}

function ForwardValidationPage({ onNavigate }: ForwardValidationPageProps) {
  const [dashboard, setDashboard] = useState<ForwardValidationDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDashboard(await userApi.forwardValidationDashboard() as ForwardValidationDashboard);
    } catch {
      setError("Forward-validation records are temporarily unavailable. Please try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function runValidation() {
    setRunning(true);
    setError(null);
    setMessage(null);
    try {
      const result = await userApi.runForwardValidation() as {
        run: ForwardValidationRun;
        dashboard: ForwardValidationDashboard;
      };
      setDashboard(result.dashboard);
      const run = result.run;
      if (run.status === "skipped") {
        setMessage(run.message || "The run was safely skipped because the latest US market candle is not complete.");
      } else {
        setMessage(`${run.signals_created} signal${run.signals_created === 1 ? "" : "s"} created, ${run.duplicates_prevented} duplicate${run.duplicates_prevented === 1 ? "" : "s"} prevented, and ${run.outcomes_updated} outcome${run.outcomes_updated === 1 ? "" : "s"} updated.`);
      }
    } catch {
      setError("Validation could not finish right now. Existing signals and paper trades were not changed.");
    } finally {
      setRunning(false);
    }
  }

  const cards = dashboard ? [
    ["Completed sample", String(dashboard.metrics.total_sample_size)],
    ["Expectancy", metric(dashboard.metrics.expectancy, "R")],
    ["Profit factor", metric(dashboard.metrics.profit_factor)],
    ["Win rate", metric(dashboard.metrics.win_rate, "%")],
    ["Maximum drawdown", metric(dashboard.metrics.maximum_drawdown, "R")],
    ["Double-cost profit factor", metric(dashboard.metrics.double_cost_profit_factor)],
  ] : [];
  const approval = dashboard?.metrics.approval;
  const completedSegments = dashboard ? Math.ceil(dashboard.sample_progress.percentage / 10) : 0;
  const lastRun = dashboard?.runner.last_run;
  const activeUniverse = dashboard?.runner.active_universe;
  const operationalCards = dashboard ? [
    ["Active universe", activeUniverse ? `${activeUniverse.name} (${activeUniverse.expected_symbols})` : "S&P 500 (503)"],
    ["Scan completion", `${(lastRun?.completion_percentage ?? 0).toFixed(2)}%`],
    ["Failed symbols", String(lastRun?.symbols_failed.length ?? 0)],
    ["Runtime", lastRun?.runtime_seconds != null ? `${lastRun.runtime_seconds.toFixed(1)}s` : "Not available yet"],
    ["Provider health", lastRun?.provider_health ?? dashboard.runner.health],
    ["Last complete market date", lastRun?.last_complete_market_date ?? "Not available yet"],
  ] : [];

  return <div className="min-h-screen bg-slate-950 font-sans text-slate-100 lg:flex">
    <Sidebar activePage="forward-validation" onNavigate={onNavigate} />
    <div className="min-w-0 flex-1">
      <Header eyebrow="Paper-only strategy research" title="Forward Validation" />
      <main className="mx-auto max-w-7xl p-5 sm:p-8">
        <section className="rounded-xl border border-amber-400/30 bg-amber-400/10 p-5">
          <p className="text-sm font-semibold text-amber-100">Forward validation and paper trading only. No live-money execution.</p>
          <p className="mt-2 text-sm leading-6 text-amber-100/70">Signals are immutable snapshots. The runner monitors completed daily candles without placing broker orders.</p>
        </section>

        {dashboard && <section className="mt-5 grid gap-4 xl:grid-cols-[1.35fr_1fr]">
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
            <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-3">
                  <h2 className="text-xl font-semibold text-white">{dashboard.strategy.name}</h2>
                  <span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2.5 py-1 text-xs font-semibold text-cyan-300">{dashboard.strategy.status}</span>
                </div>
                <p className="mt-2 text-sm text-slate-400">{dashboard.strategy.asset_class} · {dashboard.strategy.trading_style} · {dashboard.strategy.direction}</p>
                <p className="mt-1 text-xs text-slate-600">{dashboard.strategy.strategy_version}</p>
              </div>
              <button type="button" onClick={() => void runValidation()} disabled={running} className="shrink-0 rounded-lg bg-cyan-400 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60">
                {running ? "Running validation…" : "Run validation now"}
              </button>
            </div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Runner health</p>
                <p className="mt-2 text-lg font-semibold capitalize text-white">{dashboard.runner.health}</p>
              </div>
              <span className={`h-3 w-3 rounded-full ${dashboard.runner.health === "failed" ? "bg-rose-500" : dashboard.runner.health === "degraded" ? "bg-amber-400" : dashboard.runner.health === "running" ? "animate-pulse bg-amber-300" : "bg-emerald-400"}`} />
            </div>
            <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2">
              <div><dt className="text-slate-500">Last run</dt><dd className="mt-1 text-slate-300">{dateTime(dashboard.runner.last_run?.completed_at)}</dd></div>
              <div><dt className="text-slate-500">Next scheduled run</dt><dd className="mt-1 text-slate-300">{dateTime(dashboard.runner.next_scheduled_run)}</dd></div>
            </dl>
          </div>
        </section>}

        {error && <div className="mt-5 flex items-center justify-between gap-4 rounded-lg border border-rose-400/20 bg-rose-400/10 p-4 text-sm text-rose-200"><span>{error}</span><button type="button" onClick={() => void load()} className="shrink-0 font-semibold text-white hover:text-rose-100">Try again</button></div>}
        {message && <p className="mt-5 rounded-lg border border-emerald-400/20 bg-emerald-400/10 p-4 text-sm text-emerald-200">{message}</p>}
        {lastRun && lastRun.status === "partial" && <p className="mt-5 rounded-lg border border-amber-400/20 bg-amber-400/10 p-4 text-sm text-amber-100">The latest S&amp;P 500 run is incomplete. Results are visible, but runner health remains degraded until every provider failure is recovered.</p>}
        {lastRun && lastRun.status === "failed" && <p className="mt-5 rounded-lg border border-rose-400/20 bg-rose-400/10 p-4 text-sm text-rose-100">The latest S&amp;P 500 run completed fewer than 90% of symbols. Treat all results as incomplete until a successful retry finishes.</p>}

        {loading && !dashboard ? <div className="mt-5 rounded-xl border border-slate-800 bg-slate-900/40 p-6 text-sm text-slate-400">Loading forward-validation records…</div> : dashboard && <>
          <section className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {operationalCards.map(([label, value]) => <div key={label} className="rounded-xl border border-slate-800 bg-slate-900/40 p-5"><p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p><p className="mt-2 text-lg font-semibold capitalize text-white">{value}</p></div>)}
          </section>

          <section className="mt-5 rounded-xl border border-slate-800 bg-slate-900/40 p-5">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div><p className="text-xs font-medium uppercase tracking-wide text-slate-500">Approval sample</p><p className="mt-2 text-2xl font-semibold text-white">{dashboard.sample_progress.completed} <span className="text-base font-normal text-slate-500">of {dashboard.sample_progress.required} completed trades</span></p></div>
              <p className="text-sm font-semibold text-cyan-300">{dashboard.sample_progress.percentage}%</p>
            </div>
            <div className="mt-4 grid grid-cols-10 gap-1.5" aria-label={`${dashboard.sample_progress.percentage}% of the required validation sample complete`}>
              {Array.from({ length: 10 }, (_, index) => <span key={index} className={`h-2 rounded-full ${index < completedSegments ? "bg-cyan-400" : "bg-slate-800"}`} />)}
            </div>
          </section>

          <section className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {cards.map(([label, value]) => <div key={label} className="rounded-xl border border-slate-800 bg-slate-900/40 p-5"><p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p><p className="mt-2 text-2xl font-semibold text-white">{value}</p></div>)}
          </section>

          <section className={`mt-5 rounded-xl border p-5 ${approval?.approved ? "border-emerald-400/30 bg-emerald-400/10" : "border-slate-800 bg-slate-900/40"}`}>
            <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold text-white">Minimum approval rules</h2><p className="mt-1 text-sm text-slate-400">{approval?.approved ? "All mechanical paper-validation gates are satisfied." : "The strategy remains unapproved while evidence is incomplete."}</p></div><span className={`rounded-full px-3 py-1 text-xs font-semibold ${approval?.approved ? "bg-emerald-300 text-emerald-950" : "bg-slate-800 text-slate-300"}`}>{approval?.approved ? "MECHANICALLY PASSED" : "VALIDATING"}</span></div>
            <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-5">{approval && [["100 completed trades", approval.minimum_completed_trades], ["Positive expectancy", approval.positive_expectancy], ["PF above 1", approval.profit_factor_above_one], ["Acceptable drawdown", approval.acceptable_drawdown], ["Positive after double costs", approval.positive_after_double_costs]].map(([label, passed]) => <div key={String(label)} className="rounded-lg bg-slate-950/50 p-3 text-xs text-slate-300"><span className={passed ? "text-emerald-300" : "text-slate-600"}>{passed ? "●" : "○"}</span> {label}</div>)}</div>
          </section>

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
