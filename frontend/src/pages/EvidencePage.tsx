import { useEffect, useMemo, useState } from "react";

import { EvidenceCard } from "../components/EvidenceCard";
import { EvidenceFilters, type EvidenceFilterState } from "../components/EvidenceFilters";
import { EvidenceMethodology } from "../components/EvidenceMethodology";
import { EvidenceStats } from "../components/EvidenceStats";
import Header from "../components/Header";
import Sidebar, { type AppPage } from "../components/Sidebar";
import { getHistoricalEvidence } from "../services/evidence";
import type { EvidenceOutcome, EvidenceSummary } from "../types/evidence";

type EvidencePageProps = {
  onNavigate: (page: AppPage) => void;
};

const groups: Array<[EvidenceOutcome, string, string]> = [
  ["WINNER", "Winning examples", "Entered trades with a positive net R result after modeled costs and slippage."],
  ["LOSER", "Losing examples", "Entered trades with a zero or negative net R result after modeled costs and slippage."],
  ["EXPIRED", "Expired signals", "The pullback limit was not touched within the frozen three-candle entry window."],
  ["REJECTED", "Rejected signals", "The frozen regime, overlap, or risk rules prevented an entry."],
];

function initialFilters(): EvidenceFilterState {
  return {
    ticker: new URLSearchParams(window.location.search).get("ticker")?.toUpperCase() ?? "",
    sector: "",
    regime: "",
    outcome: "",
  };
}

export default function EvidencePage({ onNavigate }: EvidencePageProps) {
  const [summary, setSummary] = useState<EvidenceSummary | null>(null);
  const [filters, setFilters] = useState<EvidenceFilterState>(initialFilters);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    void getHistoricalEvidence(controller.signal)
      .then(setSummary)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Historical evidence is temporarily unavailable.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [attempt]);

  const examples = useMemo(() => {
    if (!summary) return [];
    return summary.examples.filter((example) => (
      (!filters.ticker || example.ticker === filters.ticker)
      && (!filters.sector || example.sector === filters.sector)
      && (!filters.regime || example.market_regime.historical_label === filters.regime)
      && (!filters.outcome || example.category === filters.outcome)
    ));
  }, [filters, summary]);

  return (
    <div className="min-h-screen bg-slate-950 font-sans text-slate-100 lg:flex">
      <Sidebar activePage="evidence" onNavigate={onNavigate} />
      <div className="min-w-0 flex-1">
        <Header eyebrow="Auditable strategy research" title="Historical Evidence" />
        <main className="mx-auto max-w-[96rem] space-y-6 p-5 sm:p-8">
          <section className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-3xl">
              <h2 className="text-2xl font-semibold tracking-tight text-white">See exactly how the frozen swing rules behaved</h2>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Every price level and marker is linked to bundled raw daily candles. The sample is selected from the full locked ledger by a published deterministic method—not by choosing the largest winners.
              </p>
            </div>
            {summary && (
              <div className="rounded-lg border border-emerald-400/20 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-200">
                {summary.all_audit_checks_passed ? "All evidence checks passed" : "Evidence checks require review"}
              </div>
            )}
          </section>

          {loading && !summary && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center text-sm text-slate-400">
              Verifying historical evidence…
            </div>
          )}
          {error && !summary && (
            <div className="rounded-xl border border-rose-400/20 bg-rose-400/10 p-6 text-center">
              <p className="text-sm text-rose-100">{error}</p>
              <button type="button" onClick={() => setAttempt((value) => value + 1)} className="mt-4 rounded-lg border border-rose-300/40 px-4 py-2 text-sm font-semibold text-rose-100 transition hover:bg-rose-300/10">
                Try again
              </button>
            </div>
          )}
          {error && summary && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-400/20 bg-amber-400/10 p-4 text-sm text-amber-100">
              <span>The refresh failed. The previous audited evidence remains visible.</span>
              <button type="button" onClick={() => setAttempt((value) => value + 1)} className="font-semibold text-amber-100 hover:text-white">
                Retry refresh
              </button>
            </div>
          )}

          {summary && (
            <>
              <EvidenceStats summary={summary} />
              <EvidenceMethodology summary={summary} />
              <EvidenceFilters
                filters={filters}
                tickers={summary.coverage.tickers}
                sectors={summary.coverage.sectors}
                regimes={summary.coverage.market_regimes}
                onChange={setFilters}
              />
              <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
                <p className="text-slate-400">Showing <span className="font-semibold text-white">{examples.length}</span> of {summary.example_count} deterministic examples</p>
                {(filters.ticker || filters.sector || filters.regime || filters.outcome) && <p className="text-cyan-300">Filters are active</p>}
              </div>
              {groups.map(([outcome, title, description]) => {
                const grouped = examples.filter((example) => example.category === outcome);
                if (grouped.length === 0) return null;
                return (
                  <section key={outcome} className="space-y-4">
                    <div>
                      <h2 className="text-xl font-semibold text-white">{title} <span className="text-slate-500">({grouped.length})</span></h2>
                      <p className="mt-1 text-sm text-slate-500">{description}</p>
                    </div>
                    <div className="space-y-6">
                      {grouped.map((example) => <EvidenceCard key={example.id} example={example} fullSampleSize={summary.population_statistics.accepted_trades} />)}
                    </div>
                  </section>
                );
              })}
              {examples.length === 0 && (
                <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center text-sm text-slate-400">
                  No audited examples match these filters. Clear one or more filters to continue.
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
