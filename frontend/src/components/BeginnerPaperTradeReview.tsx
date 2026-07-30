import { useEffect, useRef } from "react";

import BeginnerTerm from "./BeginnerTerm";
import type { LatestSignalEvidence } from "../types/latestSignals";
import type { TradePlan } from "../types/stock";

type Props = {
  signal: LatestSignalEvidence;
  plan: TradePlan;
  currency: string;
  loading: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: () => void;
};

const money = (value: number, currency: string) => new Intl.NumberFormat(undefined, { style: "currency", currency }).format(value);

export default function BeginnerPaperTradeReview({ signal, plan, currency, loading, error, onCancel, onConfirm }: Props) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    cancelRef.current?.focus();
    const close = (event: KeyboardEvent) => { if (event.key === "Escape" && !loading) onCancel(); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [loading, onCancel]);
  const tp1Reward = Math.max(0, plan.target_1 - plan.entry) * plan.position_size;
  const tp2Reward = Math.max(0, plan.target_2 - plan.entry) * plan.position_size;
  const failure = plan.explanation.risks[0] ?? signal.invalidation ?? "Price may reverse and reach the stop loss.";
  return <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/85 p-3 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="beginner-review-title">
    <section className="max-h-[94vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-cyan-300/30 bg-slate-900 p-5 shadow-2xl sm:p-6">
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-300">Step 3 · simulated money only</p>
      <h2 id="beginner-review-title" className="mt-1 text-2xl font-semibold text-white">Review {plan.ticker} paper trade</h2>
      <p className="mt-2 rounded-lg border border-amber-300/30 bg-amber-300/10 p-3 text-sm font-medium text-amber-100">Paper trading only. No real money will be invested. Stops and targets are reference levels and are not automatically executed.</p>
      <dl className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
        {[
          ["Amount invested", money(plan.total_position_value, currency)],
          ["Quantity", `${plan.position_size} shares`],
          ["Planned entry", money(plan.entry, currency)],
          ["Stop loss", money(plan.stop_loss, currency)],
          ["Maximum loss", money(plan.maximum_risk, currency)],
          ["Risk percentage", `${plan.account_risk_percent.toFixed(2)}%`],
          ["TP1", `${money(plan.target_1, currency)} · ${money(tp1Reward, currency)} reward`],
          ["TP2", `${money(plan.target_2, currency)} · ${money(tp2Reward, currency)} reward`],
          ["Risk / reward", `${plan.risk_reward_target_1.toFixed(2)}R / ${plan.risk_reward_target_2.toFixed(2)}R`],
        ].map(([label, value]) => <div key={label} className="rounded-lg border border-slate-700 bg-slate-950/70 p-3"><dt className="text-xs text-slate-400">{label}</dt><dd className="mt-1 font-semibold text-white">{value}</dd></div>)}
      </dl>
      <div className="mt-3 rounded-lg border border-rose-300/20 bg-rose-300/10 p-3"><p className="text-xs font-bold uppercase tracking-wide text-rose-200">Why this trade may fail</p><p className="mt-1 text-sm leading-5 text-rose-100">{failure}</p></div>
      <p className="mt-3 text-xs leading-5 text-slate-400"><BeginnerTerm term="stop loss" />, <BeginnerTerm term="target" />, and <BeginnerTerm term="risk/reward" /> are planning values. A favorable plan does not guarantee a profit.</p>
      {error && <p className="mt-3 rounded-lg border border-rose-400/30 bg-rose-400/10 p-3 text-sm text-rose-100" role="alert">{error}</p>}
      <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <button ref={cancelRef} type="button" disabled={loading} onClick={onCancel} className="rounded-lg border border-slate-600 px-4 py-2.5 font-semibold text-slate-200 outline-none hover:bg-slate-800 focus-visible:ring-2 focus-visible:ring-cyan-300 disabled:opacity-60">Cancel</button>
        <button type="button" disabled={loading} onClick={onConfirm} className="rounded-lg bg-emerald-300 px-4 py-2.5 font-bold text-slate-950 outline-none hover:bg-emerald-200 focus-visible:ring-2 focus-visible:ring-white disabled:opacity-60">{loading ? "Opening paper trade…" : "Confirm paper trade"}</button>
      </div>
    </section>
  </div>;
}
