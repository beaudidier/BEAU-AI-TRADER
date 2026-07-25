import { EvidenceChart } from "./EvidenceChart";
import type { EvidenceExample } from "../types/evidence";

type EvidenceCardProps = {
  example: EvidenceExample;
  fullSampleSize: number;
};

const outcomeTone = {
  WINNER: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  LOSER: "border-rose-400/30 bg-rose-400/10 text-rose-200",
  EXPIRED: "border-amber-400/30 bg-amber-400/10 text-amber-200",
  REJECTED: "border-slate-600 bg-slate-800 text-slate-300",
};

function price(value: number | null) {
  return value === null ? "—" : value.toFixed(4);
}

export function EvidenceCard({ example, fullSampleSize }: EvidenceCardProps) {
  const invalidation = example.rejection_or_expiry_reason
    ?? `Original stop at ${example.levels.stop_loss.toFixed(4)} invalidated the entered setup; the stop remained unchanged after TP1.`;
  const values = [
    ["Signal price", price(example.signal_price)],
    ["EMA20 / pullback", price(example.levels.proposed_pullback_entry)],
    ["EMA50", price(example.levels.ema50)],
    ["Swing low", price(example.levels.swing_low_20)],
    ["Actual entry", price(example.actual_entry_price)],
    ["Stop", price(example.levels.stop_loss)],
    ["TP1", price(example.levels.target_1)],
    ["TP2", price(example.levels.target_2)],
  ];
  return (
    <article id={`evidence-${example.id.toLowerCase()}`} className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/50">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-800 p-5">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${outcomeTone[example.category]}`}>{example.category}</span>
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{example.id}</span>
          </div>
          <h3 className="mt-3 text-xl font-semibold text-white">{example.ticker}</h3>
          <p className="mt-1 text-sm text-slate-400">{example.company_name} · {example.sector}</p>
        </div>
        <div className="text-right text-xs leading-5 text-slate-500">
          <p>{example.classification.label}</p>
          <p>Full accepted-trade sample: n={fullSampleSize.toLocaleString("en-GB")}</p>
        </div>
      </div>
      <div className="grid gap-5 p-5 2xl:grid-cols-[minmax(0,1.45fr)_minmax(22rem,0.75fr)]">
        <EvidenceChart example={example} />
        <div className="space-y-4">
          <dl className="grid grid-cols-2 gap-2">
            {values.map(([label, value]) => (
              <div key={label} className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
                <dd className="mt-1 font-mono text-sm font-semibold text-slate-100">{value}</dd>
              </div>
            ))}
          </dl>
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <div className="rounded-lg bg-slate-950/60 p-3">
              <dt className="text-xs text-slate-500">Signal timestamp</dt>
              <dd className="mt-1 text-slate-200">{example.data_timestamp}</dd>
            </div>
            <div className="rounded-lg bg-slate-950/60 p-3">
              <dt className="text-xs text-slate-500">Market regime</dt>
              <dd className="mt-1 text-slate-200">{example.market_regime.historical_label} · score {example.market_regime.engine_score.toFixed(0)}</dd>
            </div>
            <div className="rounded-lg bg-slate-950/60 p-3">
              <dt className="text-xs text-slate-500">Confidence / decision</dt>
              <dd className="mt-1 text-slate-200">{example.confidence.toFixed(0)} / {example.recommendation}</dd>
            </div>
            <div className="rounded-lg bg-slate-950/60 p-3">
              <dt className="text-xs text-slate-500">Historical result</dt>
              <dd className="mt-1 text-slate-200">{example.final_r_result === null ? "No entry" : `${example.final_r_result.toFixed(4)}R over ${example.holding_period_candles} candles`}</dd>
            </div>
          </dl>
          <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3 text-xs leading-5 text-slate-400">
            <p>Position: {example.position_sizing.position_size_shares} shares · maximum modeled risk £{example.position_sizing.maximum_monetary_risk_gbp.toFixed(2)}</p>
            <p>Costs: £{example.costs_and_slippage.total_transaction_cost_gbp.toFixed(2)} · slippage: £{example.costs_and_slippage.total_slippage_gbp.toFixed(2)}</p>
            <p>MFE / MAE: {example.maximum_favourable_excursion_r === null ? "not applicable" : `${example.maximum_favourable_excursion_r.toFixed(4)}R / ${example.maximum_adverse_excursion_r?.toFixed(4)}R`}</p>
          </div>
        </div>
      </div>
      <div className="grid gap-5 border-t border-slate-800 p-5 lg:grid-cols-2">
        <div>
          <h4 className="text-sm font-semibold text-emerald-200">Exact qualification reasons</h4>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-400">
            {example.exact_qualification_reasons.map((reason) => <li key={reason}>• {reason}</li>)}
          </ul>
        </div>
        <div className="space-y-4">
          <div>
            <h4 className="text-sm font-semibold text-amber-200">Invalidation, rejection, or expiry</h4>
            <p className="mt-3 text-sm leading-6 text-slate-400">{invalidation}</p>
          </div>
          <div>
            <h4 className="text-sm font-semibold text-white">Audited exit legs</h4>
            {example.exit_legs.length ? (
              <div className="mt-3 space-y-2">
                {example.exit_legs.map((leg, index) => (
                  <div key={`${leg.leg}-${leg.exit_date}-${index}`} className="flex flex-wrap justify-between gap-2 rounded-lg bg-slate-950/60 p-3 text-xs text-slate-400">
                    <span className="font-semibold text-slate-200">{leg.leg} · {leg.exit_date}</span>
                    <span>{leg.shares} shares at {leg.exit_price.toFixed(4)} · {leg.r_multiple.toFixed(4)}R</span>
                  </div>
                ))}
              </div>
            ) : <p className="mt-3 text-sm text-slate-500">No position was entered, so no exit legs exist.</p>}
          </div>
        </div>
      </div>
    </article>
  );
}
