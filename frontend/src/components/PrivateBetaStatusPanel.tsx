import type { PrivateBetaReadiness } from "../types/database";

type PrivateBetaStatusPanelProps = {
  status: PrivateBetaReadiness | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
};

const healthStyles: Record<string, string> = {
  operational: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  healthy: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  on_schedule: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  running: "border-cyan-400/30 bg-cyan-400/10 text-cyan-200",
  monitoring: "border-amber-400/30 bg-amber-400/10 text-amber-100",
  attention_required: "border-amber-400/30 bg-amber-400/10 text-amber-100",
  waiting: "border-slate-700 bg-slate-800/70 text-slate-300",
  awaiting_first_run: "border-slate-700 bg-slate-800/70 text-slate-300",
  degraded: "border-rose-400/30 bg-rose-400/10 text-rose-200",
  delayed: "border-rose-400/30 bg-rose-400/10 text-rose-200",
  failed: "border-rose-400/30 bg-rose-400/10 text-rose-200",
};

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) =>
    letter.toUpperCase()
  );
}

function dateTime(value: string | null) {
  if (!value) return "Awaiting first complete run";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString([], {
        dateStyle: "medium",
        timeStyle: "short",
      });
}

export default function PrivateBetaStatusPanel({
  status,
  loading,
  error,
  onRetry,
}: PrivateBetaStatusPanelProps) {
  if (!status) {
    return (
      <section className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-slate-400">
            {loading
              ? "Checking private-beta systems…"
              : error ?? "System status is temporarily unavailable."}
          </p>
          {!loading && (
            <button
              type="button"
              onClick={onRetry}
              className="rounded-lg border border-slate-700 px-3 py-2 text-xs font-semibold text-slate-200 hover:border-cyan-400/50 hover:text-cyan-200"
            >
              Retry status
            </button>
          )}
        </div>
      </section>
    );
  }

  const cards = [
    ["System", status.system_status],
    ["Market data", status.market_data_health],
    ["Scheduler", status.scheduler_health],
    ["Latest market date", status.latest_complete_market_date ?? "Pending"],
    ["Latest scan", dateTime(status.latest_scan_time)],
  ];

  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
            Private-beta status
          </p>
          <p className="mt-1 text-sm text-amber-100">
            {status.paper_trading_only_warning}
          </p>
        </div>
        <button
          type="button"
          onClick={onRetry}
          disabled={loading}
          className="rounded-lg border border-slate-700 px-3 py-2 text-xs font-semibold text-slate-200 hover:border-cyan-400/50 hover:text-cyan-200 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Refreshing…" : "Refresh status"}
        </button>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {cards.map(([cardLabel, value]) => (
          <div
            key={cardLabel}
            className="rounded-lg border border-slate-800 bg-slate-950/60 p-3"
          >
            <p className="text-xs text-slate-500">{cardLabel}</p>
            {["System", "Market data", "Scheduler"].includes(cardLabel) ? (
              <span
                className={`mt-2 inline-flex rounded-full border px-2 py-1 text-xs font-semibold ${healthStyles[value] ?? healthStyles.waiting}`}
              >
                {label(value)}
              </span>
            ) : (
              <p className="mt-1 text-sm font-semibold text-slate-100">
                {value}
              </p>
            )}
          </div>
        ))}
      </div>
      {(status.partial_scan || error) && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-400/20 bg-amber-400/10 px-3 py-2 text-xs text-amber-100">
          <span>
            {error
              ? "The latest refresh failed. The previous valid status remains visible."
              : `The latest scan is incomplete: ${status.scan_completion_percentage.toFixed(1)}% completed with ${status.failed_symbol_count} genuine failure${status.failed_symbol_count === 1 ? "" : "s"}.`}
          </span>
        </div>
      )}
    </section>
  );
}
