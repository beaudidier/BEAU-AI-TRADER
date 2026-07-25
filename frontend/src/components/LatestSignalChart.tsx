import type { LatestSignalEvidence } from "../types/latestSignals";

type LatestSignalChartProps = {
  signal: LatestSignalEvidence;
};

export default function LatestSignalChart({ signal }: LatestSignalChartProps) {
  return (
    <figure className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
      <img
        src={signal.chart.public_url}
        alt={`${signal.ticker} latest S&P 500 replay signal chart`}
        className="aspect-[30/17] w-full object-contain"
        loading="lazy"
      />
      <figcaption className="border-t border-slate-800 px-4 py-3 text-xs leading-5 text-slate-500">
        Completed daily candles from {signal.chart.window_start} through {signal.chart.window_end}. EMA20, EMA50, pullback entry, swing low, stop, TP1, TP2, and the signal marker are audited against the ledger.
      </figcaption>
    </figure>
  );
}
