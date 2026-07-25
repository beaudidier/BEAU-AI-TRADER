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

function ForwardValidationTable({ title, description, signals, emptyMessage }: ForwardValidationTableProps) {
  return <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/40">
    <div className="border-b border-slate-800 p-5"><h2 className="font-semibold text-white">{title}</h2><p className="mt-1 text-sm text-slate-500">{description}</p></div>
    <div className="overflow-x-auto">
      <table className="w-full min-w-[58rem] text-left text-sm">
        <thead className="bg-slate-900/70 text-xs uppercase tracking-wider text-slate-500"><tr>{["Ticker", "Signal", "Pullback", "Stop", "Targets", "Confidence", "Outcome"].map((heading) => <th key={heading} className="px-5 py-4 font-medium">{heading}</th>)}</tr></thead>
        <tbody className="divide-y divide-slate-800">
          {signals.map((signal) => <tr key={signal.id} className="text-slate-300">
            <td className="px-5 py-4"><p className="font-semibold text-white">{signal.ticker}</p><p className="mt-1 text-xs text-slate-500">{signal.strategy_version}</p></td>
            <td className="px-5 py-4">{money(signal.signal_price)}<p className="mt-1 text-xs text-slate-500">{new Date(signal.signal_timestamp).toLocaleDateString()}</p></td>
            <td className="px-5 py-4">{money(signal.proposed_pullback_entry)}</td>
            <td className="px-5 py-4 text-rose-200">{money(signal.stop_loss)}</td>
            <td className="px-5 py-4 text-xs">T1 {money(signal.target_1)}<br />T2 {money(signal.target_2)}</td>
            <td className="px-5 py-4"><span className="rounded-full bg-cyan-400/10 px-2.5 py-1 text-xs font-semibold text-cyan-300">{signal.confidence.toFixed(0)}</span></td>
            <td className="px-5 py-4"><span className="font-semibold text-white">{signal.outcome.status}</span><p className="mt-1 text-xs text-slate-500">{signal.outcome.status === "OPEN" ? `Open P/L ${money(signal.outcome.open_pl)}` : signal.outcome.status === "COMPLETED" ? `${(signal.outcome.realized_r ?? 0).toFixed(2)}R · ${signal.outcome.holding_days ?? 0} days` : signal.market_regime_score >= 65 ? "Risk-on regime" : signal.market_regime}</p></td>
          </tr>)}
          {signals.length === 0 && <tr><td colSpan={7} className="px-5 py-12 text-center text-slate-500">{emptyMessage}</td></tr>}
        </tbody>
      </table>
    </div>
  </section>;
}

export default ForwardValidationTable;
