import type { ForwardValidationSignal } from "../types/database";

type ForwardValidationTableProps = {
  title: string;
  description: string;
  signals: ForwardValidationSignal[];
  emptyMessage: string;
};

function money(value: number | null | undefined) {
  return value == null ? "—" : `$${value.toFixed(2)}`;
}

function statusLabel(signal: ForwardValidationSignal) {
  const status = signal.setup?.status;
  if (status) {
    return {
      waiting_for_entry: "Waiting for entry",
      entry_triggered: "Entry triggered",
      expired: "Expired",
      invalidated: "Invalidated",
      completed: "Completed",
    }[status];
  }
  return signal.outcome.status.replaceAll("_", " ");
}

function outcomeDetail(signal: ForwardValidationSignal) {
  const outcome = signal.outcome;
  if (outcome.status === "entered" || outcome.status === "TP1_hit") {
    return `Open ${Number(outcome.open_r ?? 0).toFixed(2)}R · ${outcome.holding_days ?? 0} days`;
  }
  if (["TP2_hit", "stopped", "completed"].includes(outcome.status)) {
    return `${Number(outcome.realized_r ?? 0).toFixed(2)}R · ${outcome.holding_days ?? 0} days`;
  }
  if (outcome.status === "expired") return "Entry not reached";
  if (outcome.status === "data_error") return "Will retry next run";
  return signal.expiry_date ? `Expires ${new Date(`${signal.expiry_date}T12:00:00`).toLocaleDateString()}` : "Risk-on regime";
}

function ForwardValidationTable({ title, description, signals, emptyMessage }: ForwardValidationTableProps) {
  return <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/40">
    <div className="border-b border-slate-800 p-5"><h2 className="font-semibold text-white">{title}</h2><p className="mt-1 text-sm text-slate-500">{description}</p></div>
    <div className="overflow-x-auto">
      <table className="w-full min-w-[72rem] text-left text-sm">
        <thead className="bg-slate-900/70 text-xs uppercase tracking-wider text-slate-500"><tr>{["Ticker", "Signal", "Current / entry", "Stop", "Targets", "Confidence", "Setup status"].map((heading) => <th key={heading} className="px-5 py-4 font-medium">{heading}</th>)}</tr></thead>
        <tbody className="divide-y divide-slate-800">
          {signals.map((signal) => <tr key={signal.id} className="text-slate-300">
            <td className="px-5 py-4"><p className="font-semibold text-white">{signal.ticker}</p><p className="mt-1 text-xs text-slate-500">{signal.sector ?? "Sector unavailable"}</p></td>
            <td className="px-5 py-4">{money(signal.signal_price)}<p className="mt-1 text-xs text-slate-500">{new Date(signal.signal_timestamp).toLocaleDateString()}</p></td>
            <td className="px-5 py-4"><p>{money(signal.setup?.current_price ?? signal.signal_price)} current</p><p className="mt-1 font-semibold text-cyan-200">{money(signal.proposed_pullback_entry)} planned</p><p className="mt-1 text-xs text-slate-500">{signal.setup?.distance_to_entry_label ?? "Distance unavailable"}</p></td>
            <td className="px-5 py-4 text-rose-200">{money(signal.stop_loss)}</td>
            <td className="px-5 py-4 text-xs">T1 {money(signal.target_1)}<br />T2 {money(signal.target_2)}</td>
            <td className="px-5 py-4"><span className="rounded-full bg-cyan-400/10 px-2.5 py-1 text-xs font-semibold text-cyan-300">{signal.confidence.toFixed(0)}</span></td>
            <td className="px-5 py-4"><span className={`font-semibold ${signal.setup?.status === "waiting_for_entry" ? "text-amber-200" : "text-white"}`}>{statusLabel(signal)}</span>{signal.setup?.status === "waiting_for_entry" && <p className="mt-1 text-xs font-semibold text-amber-300">Do not buy at market</p>}<p className="mt-1 text-xs text-slate-500">{outcomeDetail(signal)}</p>{signal.setup?.expiry_date && <p className="mt-1 text-xs text-slate-500">Expires {signal.setup.expiry_date}</p>}</td>
          </tr>)}
          {signals.length === 0 && <tr><td colSpan={7} className="px-5 py-12 text-center text-slate-500">{emptyMessage}</td></tr>}
        </tbody>
      </table>
    </div>
  </section>;
}

export default ForwardValidationTable;
