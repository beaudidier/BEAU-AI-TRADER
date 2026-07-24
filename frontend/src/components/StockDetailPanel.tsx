import type { Stock } from "../types/stock";
import AdviceBadge from "./AdviceBadge";
import ScoreBadge from "./ScoreBadge";

type StockDetailPanelProps = {
  stock: Stock | null;
  onClose: () => void;
};

const metrics: Array<[keyof Stock, string]> = [
  ["ema20", "EMA 20"],
  ["ema50", "EMA 50"],
  ["rsi", "RSI"],
  ["atr", "ATR"],
  ["support", "Support"],
  ["resistance", "Resistance"],
];

function StockDetailPanel({ stock, onClose }: StockDetailPanelProps) {
  if (!stock) return null;

  return (
    <div className="fixed inset-0 z-30 flex justify-end bg-slate-950/60 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label={`${stock.ticker} details`}>
      <button className="flex-1 cursor-default" onClick={onClose} aria-label="Close detail panel" />
      <section className="h-full w-full max-w-md overflow-y-auto border-l border-slate-800 bg-slate-950 p-6 shadow-2xl sm:p-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm text-slate-500">Stock details</p>
            <h2 className="mt-1 text-3xl font-semibold tracking-tight text-white">{stock.ticker}</h2>
            <p className="mt-2 text-xl font-medium text-slate-200">${stock.price.toFixed(2)}</p>
          </div>
          <button onClick={onClose} className="grid size-9 place-items-center rounded-lg border border-slate-700 text-slate-400 transition hover:border-slate-600 hover:text-white" aria-label="Close details">×</button>
        </div>
        <div className="mt-7 flex items-center gap-3"><ScoreBadge score={stock.score} /><AdviceBadge advice={stock.recommendation} /></div>
        <dl className="mt-8 grid grid-cols-2 gap-3">
          {metrics.map(([key, label]) => (
            <div key={key} className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
              <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
              <dd className="mt-1 font-mono text-sm font-semibold text-slate-200">{typeof stock[key] === "number" ? `$${(stock[key] as number).toFixed(2)}` : stock[key]}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-8">
          <h3 className="text-sm font-semibold text-white">Setup signals</h3>
          <ul className="mt-3 space-y-2">
            {stock.reasons.map((reason) => <li key={reason} className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-slate-300">{reason}</li>)}
          </ul>
        </div>
      </section>
    </div>
  );
}

export default StockDetailPanel;
