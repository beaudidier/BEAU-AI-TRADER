import type {
  PortfolioRiskDashboard,
  PortfolioRiskRejection,
} from "../types/database";

type PortfolioRiskPanelProps = {
  risk: PortfolioRiskDashboard;
  rejections?: PortfolioRiskRejection[];
  showAudit?: boolean;
};

function money(value: number) {
  return `$${value.toFixed(2)}`;
}

function PortfolioRiskPanel({
  risk,
  rejections = [],
  showAudit = true,
}: PortfolioRiskPanelProps) {
  const statusTone =
    risk.risk_status === "BLOCKED"
      ? "border-rose-400/30 bg-rose-400/10 text-rose-200"
      : risk.risk_status === "CAUTION"
        ? "border-amber-400/30 bg-amber-400/10 text-amber-100"
        : "border-emerald-400/30 bg-emerald-400/10 text-emerald-200";
  const values = [
    ["Open positions", `${risk.open_positions} / ${risk.limits.maximum_concurrent_positions}`],
    ["Open risk", `${risk.open_risk_r.toFixed(2)}R / ${risk.limits.maximum_total_open_risk_r.toFixed(0)}R`],
    ["Risk in account", money(risk.open_risk_currency)],
    ["Daily risk used", `${risk.daily_new_risk_used_r.toFixed(2)}R / ${risk.limits.maximum_daily_new_risk_r.toFixed(0)}R`],
    ["Daily risk remaining", `${risk.remaining_daily_risk_budget_r.toFixed(2)}R`],
    ["Current drawdown", `${money(risk.current_drawdown)} (${risk.current_drawdown_r.toFixed(2)}R)`],
    ["Peak equity", money(risk.peak_equity)],
    ["Risk unit", money(risk.risk_unit_currency)],
  ];

  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold text-white">Validated portfolio risk</h2>
          <p className="mt-1 text-sm text-slate-400">
            Paper-only limits. New signals are ranked by signal-time confidence.
          </p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusTone}`}>
          {risk.risk_status}
        </span>
      </div>
      <dl className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {values.map(([label, value]) => (
          <div key={label} className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
            <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
            <dd className="mt-1 text-sm font-semibold text-white">{value}</dd>
          </div>
        ))}
      </dl>
      {risk.blocked_reasons.length > 0 && (
        <div className="mt-4 rounded-lg border border-rose-400/20 bg-rose-400/10 p-4">
          <p className="text-sm font-semibold text-rose-200">New paper risk is blocked</p>
          <ul className="mt-2 space-y-1 text-sm text-rose-100">
            {risk.blocked_reasons.map((reason) => <li key={reason}>{reason}</li>)}
          </ul>
          <p className="mt-3 text-xs text-rose-200/70">
            Daily capacity resets {new Date(risk.capacity_resets_at).toLocaleString()}.
            {risk.limiting_positions[0] ? ` The largest active risk is ${risk.limiting_positions[0].ticker} at ${risk.limiting_positions[0].remaining_risk_r.toFixed(2)}R.` : ""}
          </p>
        </div>
      )}
      {showAudit && (
        <div className="mt-5 border-t border-slate-800 pt-5">
          <h3 className="text-sm font-semibold text-white">Blocked signal audit</h3>
          <p className="mt-1 text-xs text-slate-500">
            Rejected setups remain visible and are never silently dropped.
          </p>
          <div className="mt-3 space-y-2">
            {rejections.slice(0, 20).map((item) => (
              <article key={item.id} className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-white">
                    {item.ticker} · rank {item.signal_rank}
                  </p>
                  <time className="text-xs text-slate-500">{new Date(item.rejected_at).toLocaleString()}</time>
                </div>
                <p className="mt-2 text-xs leading-5 text-slate-300">{item.rejection_reason}</p>
                <p className="mt-2 text-xs text-slate-500">
                  {item.current_open_positions} open · {item.current_open_risk_r.toFixed(2)}R open risk · {item.daily_new_risk_r.toFixed(2)}R daily risk
                  {item.limiting_reference ? ` · limit caused by ${item.limiting_reference}` : ""}
                </p>
              </article>
            ))}
            {rejections.length === 0 && (
              <p className="text-sm text-slate-500">No setups have been blocked by portfolio limits.</p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

export default PortfolioRiskPanel;
