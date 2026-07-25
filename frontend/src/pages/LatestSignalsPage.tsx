import { useEffect, useState } from "react";

import Header from "../components/Header";
import LatestSignalCard from "../components/LatestSignalCard";
import LatestSignalMethodology from "../components/LatestSignalMethodology";
import SectorConcentrationBanner from "../components/SectorConcentrationBanner";
import Sidebar, { type AppPage } from "../components/Sidebar";
import { getLatestSignalEvidence } from "../services/latestSignals";
import type { LatestSignalEvidenceSummary } from "../types/latestSignals";

type LatestSignalsPageProps = {
  onNavigate: (page: AppPage) => void;
};

export default function LatestSignalsPage({ onNavigate }: LatestSignalsPageProps) {
  const [summary, setSummary] = useState<LatestSignalEvidenceSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    void getLatestSignalEvidence(controller.signal)
      .then(setSummary)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Latest signal evidence is temporarily unavailable.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [attempt]);

  return (
    <div className="min-h-screen bg-slate-950 font-sans text-slate-100 lg:flex">
      <Sidebar activePage="latest-signals" onNavigate={onNavigate} />
      <div className="min-w-0 flex-1">
        <Header eyebrow="Latest production-path replay" title="Latest Signal Evidence" />
        <main className="mx-auto max-w-[96rem] space-y-6 p-5 sm:p-8">
          <section className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-3xl">
              <h2 className="text-2xl font-semibold tracking-tight text-white">Every valid signal from the latest complete S&amp;P 500 replay</h2>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Inspect the raw-candle levels, exact qualification reasons, risk, confidence, and chart evidence before opening the live analysis workspace.
              </p>
            </div>
            {summary && <div className={`rounded-lg border px-4 py-3 text-sm ${summary.all_checks_passed ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-200" : "border-rose-400/20 bg-rose-400/10 text-rose-200"}`}>{summary.all_checks_passed ? "All validation checks passed" : "Evidence requires review"}</div>}
          </section>

          {loading && !summary && <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center text-sm text-slate-400">Auditing latest replay signals…</div>}
          {error && !summary && <div className="rounded-xl border border-rose-400/20 bg-rose-400/10 p-6 text-center"><p className="text-sm text-rose-100">{error}</p><button type="button" onClick={() => setAttempt((value) => value + 1)} className="mt-4 rounded-lg border border-rose-300/40 px-4 py-2 text-sm font-semibold text-rose-100 transition hover:bg-rose-300/10">Try again</button></div>}

          {summary && <>
            <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {[["Signals audited", String(summary.signal_count)], ["Replay date", summary.replay_date], ["Sectors covered", String(summary.sectors.length)], ["Mismatches", String(summary.mismatches.length)]].map(([label, value]) => <div key={label} className="rounded-xl border border-slate-800 bg-slate-900/50 p-5"><p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p><p className="mt-2 text-xl font-semibold text-white">{value}</p></div>)}
            </section>
            <SectorConcentrationBanner concentration={summary.concentration} />
            <LatestSignalMethodology summary={summary} />
            <section className="space-y-6">
              {summary.signals.map((signal) => <LatestSignalCard key={signal.id} signal={signal} />)}
            </section>
          </>}
        </main>
      </div>
    </div>
  );
}
