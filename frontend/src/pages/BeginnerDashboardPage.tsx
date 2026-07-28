import { useCallback, useEffect, useMemo, useState } from "react";

import BeginnerPaperTradeReview from "../components/BeginnerPaperTradeReview";
import BeginnerTerm from "../components/BeginnerTerm";
import ModeSwitcher from "../components/ModeSwitcher";
import Sidebar, { type AppPage } from "../components/Sidebar";
import { beginnerSafety, educationTerms, paperTradePayload, selectBestSetup } from "../services/beginnerMode";
import { getTradePlan } from "../services/api";
import { getLatestSignalEvidence } from "../services/latestSignals";
import { userApi } from "../services/userApi";
import type { PaperPortfolio, UserSettings } from "../types/database";
import type { LatestSignalEvidence, LatestSignalEvidenceSummary } from "../types/latestSignals";
import type { TradePlan } from "../types/stock";

type Props = { onNavigate: (page: AppPage) => void };
const money = (value: number, currency: string) => new Intl.NumberFormat(undefined, { style: "currency", currency }).format(value);

export default function BeginnerDashboardPage({ onNavigate }: Props) {
  const [summary, setSummary] = useState<LatestSignalEvidenceSummary | null>(null);
  const [plan, setPlan] = useState<TradePlan | null>(null);
  const [portfolio, setPortfolio] = useState<PaperPortfolio | null>(null);
  const [settings, setSettings] = useState<Partial<UserSettings>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [opening, setOpening] = useState(false);
  const [tradeError, setTradeError] = useState<string | null>(null);
  const [opened, setOpened] = useState(false);
  const signal = useMemo(() => selectBestSetup(summary?.signals ?? []), [summary]);
  const currency = settings.preferred_currency ?? "USD";

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [signalSummary, paperPortfolio, userSettings] = await Promise.all([
        getLatestSignalEvidence(),
        userApi.paperPortfolio() as Promise<PaperPortfolio>,
        userApi.settings() as Promise<UserSettings>,
      ]);
      const best = selectBestSetup(signalSummary.signals);
      const tradePlan = best ? await getTradePlan(best.ticker) : null;
      setSummary(signalSummary);
      setPortfolio(paperPortfolio);
      setSettings(userSettings);
      setPlan(tradePlan);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Beginner Mode could not load a verified setup.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);
  const safety = signal ? beginnerSafety(signal, plan, portfolio) : null;

  async function confirmTrade() {
    if (!plan || !safety?.canReview) return;
    setOpening(true);
    setTradeError(null);
    try {
      await userApi.openPaperTrade(paperTradePayload(plan));
      setOpened(true);
      setReviewing(false);
      setPortfolio(await userApi.paperPortfolio() as PaperPortfolio);
    } catch (reason) {
      setTradeError(reason instanceof Error ? reason.message : "The paper trade could not be opened.");
    } finally {
      setOpening(false);
    }
  }

  return <div className="min-h-screen bg-slate-950 font-sans text-slate-100 lg:flex">
    <Sidebar activePage="dashboard" onNavigate={onNavigate} />
    <main className="min-w-0 flex-1 p-4 sm:p-6 lg:h-screen lg:overflow-y-auto">
      <div className="mx-auto max-w-6xl">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div><p className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-300">Beginner Mode · paper trading only</p><h1 className="mt-1 text-2xl font-semibold text-white">One setup. Clear risk. No real money.</h1></div>
          <ModeSwitcher />
        </header>
        <section className="mt-4 grid grid-cols-3 gap-2" aria-label="First trade onboarding">
          {["Find a setup", "Understand the risk", "Open a paper trade"].map((step, index) => <div key={step} className={`rounded-lg border p-2.5 ${index === 0 || (index === 1 && signal) || (index === 2 && safety?.canReview) ? "border-cyan-300/40 bg-cyan-300/10" : "border-slate-700 bg-slate-900"}`}><p className="text-[0.65rem] font-bold uppercase tracking-wide text-slate-400">Step {index + 1}</p><p className="mt-0.5 text-xs font-semibold text-white sm:text-sm">{step}</p></div>)}
        </section>
        {loading && <section className="mt-4 rounded-2xl border border-slate-700 bg-slate-900/70 p-8 text-center text-slate-300">Finding the best verified setup and checking every safety limit…</section>}
        {error && <section className="mt-4 rounded-2xl border border-rose-300/30 bg-rose-300/10 p-5"><h2 className="font-semibold text-rose-100">No action is available</h2><p className="mt-1 text-sm text-rose-100">{error}</p><button type="button" onClick={() => void load()} className="mt-3 rounded-lg border border-rose-200/50 px-4 py-2 text-sm font-semibold outline-none focus-visible:ring-2 focus-visible:ring-white">Try again</button></section>}
        {!loading && !error && !signal && <section className="mt-4 rounded-2xl border border-slate-700 bg-slate-900 p-8 text-center"><h2 className="font-semibold">No eligible setup right now</h2><p className="mt-2 text-sm text-slate-400">The strategy did not find a setup that passed its rules. No action is needed.</p></section>}
        {signal && safety && plan && <SetupCard signal={signal} plan={plan} currency={currency} safety={safety} onReview={() => { setTradeError(null); setReviewing(true); }} />}
        {opened && <div className="mt-3 flex items-center justify-between gap-3 rounded-xl border border-emerald-300/30 bg-emerald-300/10 p-3 text-sm text-emerald-100"><span>Paper trade opened. No real money was used.</span><button type="button" onClick={() => onNavigate("paper-trading")} className="font-bold underline">View Paper Portfolio</button></div>}
        <nav className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4" aria-label="Beginner shortcuts">
          {[["Advanced Analysis", "latest-signals"], ["Historical Evidence", "evidence"], ["Paper Portfolio", "paper-trading"], ["Learning", "learning"]].map(([label, page]) => <button key={label} type="button" onClick={() => onNavigate(page as AppPage)} className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm font-semibold text-slate-200 outline-none hover:border-cyan-300/50 hover:text-white focus-visible:ring-2 focus-visible:ring-cyan-300">{label}</button>)}
        </nav>
        <details className="mt-4 rounded-xl border border-slate-800 bg-slate-900/60 p-4"><summary className="cursor-pointer text-sm font-semibold text-cyan-200 outline-none focus-visible:ring-2 focus-visible:ring-cyan-300">Trading words in plain language</summary><dl className="mt-3 grid gap-2 sm:grid-cols-2">{Object.entries(educationTerms).map(([term, explanation]) => <div key={term}><dt className="text-sm font-semibold capitalize text-white">{term}</dt><dd className="text-xs leading-5 text-slate-400">{explanation}</dd></div>)}</dl></details>
      </div>
    </main>
    {reviewing && signal && plan && <BeginnerPaperTradeReview signal={signal} plan={plan} currency={currency} loading={opening} error={tradeError} onCancel={() => { if (!opening) setReviewing(false); }} onConfirm={() => void confirmTrade()} />}
  </div>;
}

function SetupCard({ signal, plan, currency, safety, onReview }: { signal: LatestSignalEvidence; plan: TradePlan; currency: string; safety: ReturnType<typeof beginnerSafety>; onReview: () => void }) {
  const tp1 = Math.max(0, plan.target_1 - plan.entry) * plan.position_size;
  const tp2 = Math.max(0, plan.target_2 - plan.entry) * plan.position_size;
  const reason = signal.setup.beginner_explanation.why_setup_exists || signal.qualification_reasons[0];
  const risk = plan.explanation.risks[0] || signal.invalidation;
  const tone = safety.status === "ready" ? "border-emerald-300/40" : safety.status === "waiting" ? "border-amber-300/40" : "border-rose-300/40";
  return <article className={`mt-4 rounded-2xl border ${tone} bg-slate-900/80 p-4 shadow-xl shadow-black/20 sm:p-5`}>
    <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wide text-slate-400">Best eligible setup</p><h2 className="mt-1 text-3xl font-bold text-white">{signal.ticker} <span className="text-base font-medium text-slate-400">{signal.company_name}</span></h2></div><div className="text-right"><p className="text-xs font-bold uppercase text-slate-400">Status</p><p className="mt-1 font-bold capitalize text-white">{safety.status}</p></div></div>
    <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
      <Metric label="Recommendation" value={plan.recommendation} />
      <Metric label={<BeginnerTerm term="confidence">Confidence</BeginnerTerm>} value={`${plan.confidence_score.toFixed(0)}/100`} note="Not a probability of profit" />
      <Metric label="Current price" value={money(signal.current_price, currency)} />
      <Metric label={<BeginnerTerm term="entry">Planned entry</BeginnerTerm>} value={money(plan.entry, currency)} />
      <Metric label="Maximum possible loss" value={money(plan.maximum_risk, currency)} />
      <Metric label={<BeginnerTerm term="target">Profit at TP1</BeginnerTerm>} value={money(tp1, currency)} />
      <Metric label={<BeginnerTerm term="target">Profit at TP2</BeginnerTerm>} value={money(tp2, currency)} />
      <Metric label={<BeginnerTerm term="position size">Position size</BeginnerTerm>} value={`${plan.position_size} shares`} />
    </div>
    <div className="mt-3 grid gap-2 sm:grid-cols-2"><div className="rounded-lg bg-slate-950/70 p-3"><p className="text-xs font-bold uppercase text-cyan-300">Why it may work</p><p className="mt-1 text-sm leading-5 text-slate-300">{reason}</p></div><div className="rounded-lg border border-rose-300/20 bg-rose-300/10 p-3"><p className="text-xs font-bold uppercase text-rose-200">Biggest risk</p><p className="mt-1 text-sm leading-5 text-rose-100">{risk}</p></div></div>
    <p className="mt-2 text-xs text-slate-400">This <BeginnerTerm term="pullback" /> setup was assessed within a <BeginnerTerm term="market regime">{signal.market_regime} market regime</BeginnerTerm>. These labels are context, not guarantees.</p>
    {safety.reasons.length > 0 && <ul className="mt-3 space-y-1 rounded-lg border border-amber-300/20 bg-amber-300/10 p-3 text-xs text-amber-100">{safety.reasons.map((item) => <li key={item}>• {item}</li>)}</ul>}
    <button type="button" disabled={!safety.canReview} onClick={onReview} className="mt-3 w-full rounded-xl bg-cyan-300 px-4 py-3 text-base font-bold text-slate-950 outline-none hover:bg-cyan-200 focus-visible:ring-2 focus-visible:ring-white disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-300">{safety.action}</button>
    <p className="mt-2 text-center text-xs text-slate-400"><BeginnerTerm term="paper trading">Paper trading</BeginnerTerm> only · no real-money action is available.</p>
  </article>;
}

function Metric({ label, value, note }: { label: React.ReactNode; value: string; note?: string }) {
  return <div className="rounded-lg border border-slate-700 bg-slate-950/70 p-2.5"><p className="text-[0.68rem] font-medium uppercase tracking-wide text-slate-400">{label}</p><p className="mt-1 text-sm font-bold text-white">{value}</p>{note && <p className="mt-0.5 text-[0.65rem] text-amber-200">{note}</p>}</div>;
}
