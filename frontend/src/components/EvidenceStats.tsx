import type { EvidenceSummary } from "../types/evidence";

type EvidenceStatsProps = {
  summary: EvidenceSummary;
};

function number(value: number) {
  return new Intl.NumberFormat("en-GB").format(value);
}

export function EvidenceStats({ summary }: EvidenceStatsProps) {
  const stats = summary.population_statistics;
  const cards = [
    ["Accepted trades", number(stats.accepted_trades), `${stats.wins} wins · ${stats.losses} losses`],
    ["Win rate", `${stats.win_rate.toFixed(2)}%`, `n=${number(stats.accepted_trades)} accepted trades`],
    ["Expectancy", `${stats.expectancy_r.toFixed(4)}R`, `95% CI ${stats.expectancy_95_ci[0].toFixed(4)}R to ${stats.expectancy_95_ci[1].toFixed(4)}R`],
    ["Profit factor", stats.profit_factor.toFixed(4), `n=${number(stats.accepted_trades)} accepted trades`],
    ["Maximum drawdown", `${stats.maximum_drawdown_r.toFixed(4)}R`, "Chronological full-ledger equity curve"],
    ["Signal population", number(stats.candidate_signals), `${number(stats.rejected_signals)} did not become trades`],
  ];
  return (
    <section>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        {cards.map(([label, value, detail]) => (
          <article key={label} className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
            <p className="mt-2 text-xl font-semibold text-white">{value}</p>
            <p className="mt-2 text-xs leading-5 text-slate-500">{detail}</p>
          </article>
        ))}
      </div>
      <p className="mt-3 rounded-lg border border-amber-400/20 bg-amber-400/10 px-4 py-3 text-xs leading-5 text-amber-100">
        Retrospective holdout, out-of-sample test. Statistics describe all {number(stats.accepted_trades)} accepted trades, while the charts below are a deterministic 30-example audit sample. This is not forward validation and does not guarantee future results.
      </p>
    </section>
  );
}
