import type { EvidenceSummary } from "../types/evidence";

type EvidenceMethodologyProps = {
  summary: EvidenceSummary;
};

export function EvidenceMethodology({ summary }: EvidenceMethodologyProps) {
  const selection = summary.selection;
  const rules = summary.strategy.rules;
  return (
    <details className="rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-5" open>
      <summary className="cursor-pointer font-semibold text-white">Methodology and limitations</summary>
      <div className="mt-4 grid gap-5 text-sm leading-6 text-slate-300 lg:grid-cols-2">
        <div className="min-w-0">
          <h3 className="font-semibold text-cyan-200">Selection</h3>
          <p className="mt-2">
            All {selection.candidate_population.toLocaleString("en-GB")} records in the locked out-of-sample ledger were eligible. Fixed quotas selected 10 winners, 10 losers, 5 expired signals, and 5 rejected signals. The algorithm balances outcome, sector, regime, and year, then uses a published seeded SHA-256 tie-breaker. It never ranks candidates by profit magnitude.
          </p>
          <p className="mt-2 text-slate-400">
            The sample is deliberately balanced for audit coverage, not weighted to reproduce population frequencies. Use the full-ledger statistics above—not the 30 cards—to estimate historical rates.
          </p>
          <p className="mt-2 break-all text-slate-400">
            Deterministic replay: {selection.deterministic_replay_verified ? "verified" : "not verified"} · digest {selection.selected_keys_sha256}
          </p>
          <p className="mt-2 text-slate-400">{selection.milestone_34_audit.finding} {selection.milestone_34_audit.resolution}</p>
        </div>
        <div className="min-w-0">
          <h3 className="font-semibold text-cyan-200">Test classification</h3>
          <p className="mt-2">
            Every chart is retrospective holdout and out-of-sample evidence from {summary.classification.holdout_window.start} through {summary.classification.holdout_window.end}. None is a live forward-validation example.
          </p>
          <p className="mt-2">
            Execution includes {rules.slippage_bps_per_side} bps slippage and {rules.transaction_cost_bps_per_side} bps transaction cost per side. Half exits at TP1, the original stop remains for the balance, and a stop is assumed first when stop and target occur in the same candle.
          </p>
        </div>
        <div className="min-w-0 lg:col-span-2">
          <h3 className="font-semibold text-amber-200">Limitations</h3>
          <p className="mt-2 text-slate-400">
            Daily candles do not reveal intraday event order beyond the conservative stop-first rule. Historical constituents may introduce survivorship bias. Fills are simulated, liquidity and tax effects are not modeled, and the £10,000 position examples treat historical US price units as GBP-equivalent without historical currency conversion. A selected example is evidence of past rule behavior, not a prediction or promise of profit.
          </p>
        </div>
      </div>
    </details>
  );
}
