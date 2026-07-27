import type { Stock } from "../types/stock";
import AdviceBadge from "./AdviceBadge";
import ScoreBadge from "./ScoreBadge";

type StockTableProps = {
  stocks: Stock[];
  onOpenChart: (stock: Stock) => void;
  onViewDetails: (stock: Stock) => void;
};

function StockTable({ stocks, onOpenChart, onViewDetails }: StockTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[41.25rem] text-left text-sm">
        <thead className="border-y border-slate-800 bg-slate-900/50 text-xs uppercase tracking-wider text-slate-500">
          <tr>
            <th className="px-5 py-4 font-medium">Ticker</th>
            <th className="px-5 py-4 font-medium">Daily close</th>
            <th className="px-5 py-4 font-medium">Score</th>
            <th className="px-5 py-4 font-medium">Advice</th>
            <th className="px-5 py-4 text-right font-medium">Details</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {stocks.map((stock) => (
            <tr key={stock.ticker} className="cursor-pointer text-slate-300 transition hover:bg-slate-800/70" onClick={() => onOpenChart(stock)}>
              <td className="px-5 py-4 font-semibold text-white">{stock.ticker}</td>
              <td className="px-5 py-4 tabular-nums" title="Validated completed daily-candle price">${stock.price.toFixed(2)}</td>
              <td className="px-5 py-4"><ScoreBadge score={stock.score} /></td>
              <td className="px-5 py-4"><AdviceBadge advice={stock.recommendation} /></td>
              <td className="px-5 py-4 text-right"><button type="button" onClick={(event) => { event.stopPropagation(); onViewDetails(stock); }} className="font-medium text-cyan-300 transition hover:text-cyan-200">Details <span aria-hidden="true">→</span></button></td>
            </tr>
          ))}
          {stocks.length === 0 && (
            <tr><td colSpan={5} className="px-5 py-12 text-center text-slate-500">No matching stocks found.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default StockTable;
