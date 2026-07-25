import type { EvidenceOutcome } from "../types/evidence";

export type EvidenceFilterState = {
  ticker: string;
  sector: string;
  regime: string;
  outcome: EvidenceOutcome | "";
};

type EvidenceFiltersProps = {
  filters: EvidenceFilterState;
  tickers: string[];
  sectors: string[];
  regimes: string[];
  onChange: (filters: EvidenceFilterState) => void;
};

const outcomes: EvidenceOutcome[] = ["WINNER", "LOSER", "EXPIRED", "REJECTED"];

export function EvidenceFilters({ filters, tickers, sectors, regimes, onChange }: EvidenceFiltersProps) {
  const selectClass = "h-10 rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm text-slate-200 outline-none transition focus:border-cyan-400";
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/50 p-4" aria-label="Evidence filters">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <label className="grid gap-1.5 text-xs font-medium uppercase tracking-wide text-slate-500">
          Ticker
          <select value={filters.ticker} onChange={(event) => onChange({ ...filters, ticker: event.target.value })} className={selectClass}>
            <option value="">All tickers</option>
            {tickers.map((ticker) => <option key={ticker} value={ticker}>{ticker}</option>)}
          </select>
        </label>
        <label className="grid gap-1.5 text-xs font-medium uppercase tracking-wide text-slate-500">
          Sector
          <select value={filters.sector} onChange={(event) => onChange({ ...filters, sector: event.target.value })} className={selectClass}>
            <option value="">All sectors</option>
            {sectors.map((sector) => <option key={sector} value={sector}>{sector}</option>)}
          </select>
        </label>
        <label className="grid gap-1.5 text-xs font-medium uppercase tracking-wide text-slate-500">
          Regime
          <select value={filters.regime} onChange={(event) => onChange({ ...filters, regime: event.target.value })} className={selectClass}>
            <option value="">All regimes</option>
            {regimes.map((regime) => <option key={regime} value={regime}>{regime}</option>)}
          </select>
        </label>
        <label className="grid gap-1.5 text-xs font-medium uppercase tracking-wide text-slate-500">
          Outcome
          <select value={filters.outcome} onChange={(event) => onChange({ ...filters, outcome: event.target.value as EvidenceOutcome | "" })} className={selectClass}>
            <option value="">All outcomes</option>
            {outcomes.map((outcome) => <option key={outcome} value={outcome}>{outcome}</option>)}
          </select>
        </label>
        <button
          type="button"
          onClick={() => onChange({ ticker: "", sector: "", regime: "", outcome: "" })}
          className="self-end rounded-lg border border-slate-700 px-3 py-2.5 text-sm font-semibold text-slate-300 transition hover:border-slate-500 hover:text-white"
        >
          Clear filters
        </button>
      </div>
    </section>
  );
}
