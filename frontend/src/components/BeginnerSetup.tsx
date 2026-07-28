import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { getLatestSignalEvidence } from "../services/latestSignals";
import { isStalePrice, setupPresentation } from "../services/setupPresentation";
import { userApi } from "../services/userApi";
import type { LatestSignalEvidence } from "../types/latestSignals";

function money(value: number) {
  return `$${value.toFixed(2)}`;
}

export default function BeginnerSetup() {
  const [signal, setSignal] = useState<LatestSignalEvidence | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [portfolioBlocked, setPortfolioBlocked] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    void getLatestSignalEvidence(controller.signal)
      .then((summary) => {
        if (controller.signal.aborted) return;
        const ranked = [...summary.signals].sort((a, b) => b.confidence - a.confidence);
        setError(false);
        setSignal(ranked[0] ?? null);
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(true);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    let active = true;
    void userApi.paperPortfolio()
      .then((portfolio) => {
        if (active) setPortfolioBlocked(portfolio?.portfolio_risk?.risk_status === "BLOCKED");
      })
      .catch(() => {
        if (active) setPortfolioBlocked(false);
      });
    return () => { active = false; };
  }, []);

  const stale = signal ? isStalePrice(signal.setup.current_price_timestamp) : false;
  const state = useMemo(
    () => signal ? setupPresentation(signal.setup_status, signal.planned_entry, { portfolioBlocked, stale }) : null,
    [portfolioBlocked, signal, stale],
  );

  if (loading) return <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-8 text-sm text-slate-300">Finding the clearest current setup…</section>;
  if (error) return <section data-tour="setup-empty" className="rounded-2xl border border-amber-400/30 bg-amber-400/10 p-8"><h2 className="text-xl font-semibold text-white">Data unavailable</h2><p className="mt-2 text-sm text-amber-100">Do not act until current prices and trade levels can be verified. Try refreshing later.</p></section>;
  if (!signal) return <section data-tour="setup-empty" className="rounded-2xl border border-slate-800 bg-slate-900/60 p-8"><h2 className="text-xl font-semibold text-white">No valid setup today</h2><p className="mt-2 text-sm text-slate-400">Nothing passed every strategy rule. The correct action is to wait—no trade is better than a forced trade.</p></section>;

  const riskPerShare = Math.max(0, signal.planned_entry - signal.levels.stop);
  const rewardOne = Math.max(0, signal.levels.tp1 - signal.planned_entry);
  const rewardTwo = Math.max(0, signal.levels.tp2 - signal.planned_entry);
  const tone = state?.tone === "emerald" ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-100" : state?.tone === "rose" ? "border-rose-400/30 bg-rose-400/10 text-rose-100" : state?.tone === "amber" ? "border-amber-400/30 bg-amber-400/10 text-amber-100" : "border-slate-700 bg-slate-800/60 text-slate-200";

  return (
    <section className="overflow-hidden rounded-2xl border border-cyan-400/20 bg-slate-900/60 shadow-2xl shadow-slate-950/40">
      <div className="border-b border-slate-800 p-5 sm:p-7">
        <p className="text-sm font-semibold text-cyan-300">What should I do now?</p>
        <div data-tour="best-setup" className="mt-3 flex flex-wrap items-start justify-between gap-4">
          <div><h2 className="text-3xl font-semibold text-white">{signal.ticker} <span className="text-lg font-normal text-slate-400">· {signal.company_name}</span></h2><p className="mt-2 text-sm text-slate-400">The single highest-ranked verified setup available.</p></div>
          <span data-tour="setup-status" className={`rounded-full border px-4 py-2 text-sm font-bold ${tone}`}>{state?.label}</span>
        </div>
        <div className={`mt-5 rounded-xl border p-4 ${tone}`}><p className="text-xs font-bold uppercase tracking-wider">Your next action</p><p className="mt-1 text-lg font-semibold">{state?.action}</p>{state?.label === "Waiting for entry" && <p className="mt-1 text-sm opacity-80">Do not buy at the current market price. If entry is never reached, no trade opens.</p>}</div>
        {stale && <p className="mt-3 rounded-lg border border-rose-300/30 bg-rose-400/10 p-3 text-sm leading-6 text-rose-100">Price data is from {new Date(signal.setup.current_price_timestamp ?? signal.data_timestamp).toLocaleString()}. It is too old to act on. Wait for refreshed data.</p>}
        {portfolioBlocked && <p className="mt-3 rounded-lg border border-rose-300/30 bg-rose-400/10 p-3 text-sm leading-6 text-rose-100">Your existing paper portfolio has reached a risk limit. Review portfolio risk before considering another trade.</p>}
      </div>

      <div className="p-5 sm:p-7">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["Current price", money(signal.current_price), "Where the stock is now", "current-price"],
            ["Planned entry", money(signal.planned_entry), "Only act if price reaches this level", "planned-entry"],
            ["Stop", money(signal.levels.stop), "Exit level if the idea fails", "stop-loss"],
            ["TP1", money(signal.levels.tp1), "First planned profit target", "tp1"],
            ["TP2", money(signal.levels.tp2), "Second planned profit target", "tp2"],
          ].map(([label, value, help, tour]) => <div key={label} data-tour={tour} className="rounded-xl border border-slate-800 bg-slate-950/60 p-4"><p className="text-xs text-slate-500">{label} <span title={`About ${label}`} aria-label={`What is this? ${label}`}>ⓘ</span></p><p className="mt-1 text-xl font-semibold text-white">{value}</p><p className="mt-2 text-xs leading-5 text-slate-400">{help}</p></div>)}
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div data-tour="maximum-loss" className="rounded-xl border border-rose-400/20 bg-rose-400/5 p-4"><p className="text-xs font-semibold text-rose-300">Maximum possible loss <span title="What is this? Planned loss per share before slippage." aria-label="What is this? Maximum possible loss">ⓘ</span></p><p className="mt-1 text-xl font-semibold text-white">{money(riskPerShare)} per share</p><p className="mt-1 text-xs text-slate-400">Before slippage; total loss depends on share quantity.</p></div>
          <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/5 p-4"><p className="text-xs font-semibold text-emerald-300">Possible reward</p><p className="mt-1 text-xl font-semibold text-white">{money(rewardOne)} / {money(rewardTwo)} per share</p><p className="mt-1 text-xs text-slate-400">At TP1 / TP2; targets are not guaranteed.</p></div>
        </div>

        <div className="mt-5 grid gap-3 lg:grid-cols-2">
          {[
            ["Why this trade?", signal.setup.beginner_explanation.why_setup_exists],
            ["Why wait?", signal.setup.beginner_explanation.why_waiting_matters],
            ["What would invalidate it?", signal.invalidation],
            ["What if price never reaches entry?", signal.setup.beginner_explanation.if_price_never_reaches_entry],
            ["Why is the stop there?", `The stop sits below the setup’s swing low (${money(signal.levels.swing_low)}). Reaching it means the price structure behind the idea has failed.`],
            ["Why are TP1 and TP2 there?", `They are rules-based reward levels at ${signal.risk_reward_target_1.toFixed(1)} and ${signal.risk_reward_target_2.toFixed(1)} times the amount risked per share.`],
          ].map(([title, body]) => <div key={title} className="rounded-xl border border-slate-800 bg-slate-950/40 p-4"><h3 className="text-sm font-semibold text-white">{title}</h3><p className="mt-2 text-sm leading-6 text-slate-400">{body}</p></div>)}
        </div>

        <div className="mt-5 rounded-xl border border-slate-700 bg-slate-950/70 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Biggest risk</p>
          <p className="mt-2 text-sm text-white">Price can gap below the stop, so the actual loss can exceed the planned amount. Paper trade first.</p>
        </div>

        <ol className="mt-5 grid gap-3 sm:grid-cols-3">
          {["Understand the setup", "Understand the risk", "Open a paper trade"].map((label, index) => <li key={label} className="rounded-xl border border-slate-800 bg-slate-950/40 p-4"><span className="text-xs font-bold text-cyan-300">STEP {index + 1}</span><p className="mt-1 text-sm font-semibold text-white">{label}</p></li>)}
        </ol>
        <div data-tour="workspace-link" className="mt-5 flex flex-wrap gap-3">
          <Link data-tour="next-action" to={`/workspace/${encodeURIComponent(signal.ticker)}`} className="min-h-11 rounded-lg bg-cyan-400 px-5 py-3 text-sm font-bold text-slate-950 hover:bg-cyan-300">Review chart and risk</Link>
          <Link to="/latest-signals" className="rounded-lg border border-slate-700 px-5 py-3 text-sm font-semibold text-slate-200 hover:bg-slate-800">See all setups</Link>
        </div>
        <p className="mt-5 rounded-lg border border-cyan-400/20 bg-cyan-400/5 p-3 text-xs leading-5 text-cyan-100">Confidence is a rules-based score, not a guaranteed probability of profit.</p>
      </div>
    </section>
  );
}
