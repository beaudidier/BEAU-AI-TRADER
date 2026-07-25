import type { EvidenceExample } from "../types/evidence";

type EvidenceChartProps = {
  example: EvidenceExample;
};

export function EvidenceChart({ example }: EvidenceChartProps) {
  return (
    <figure className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
      <img
        src={example.chart.public_url}
        alt={`${example.ticker} ${example.category.toLowerCase()} historical candlestick evidence`}
        className="aspect-[30/17] w-full object-contain"
        loading="lazy"
      />
      <figcaption className="border-t border-slate-800 px-4 py-3 text-xs leading-5 text-slate-500">
        Daily candles, EMA20, EMA50, frozen pullback levels, signal marker, and audited execution markers.
      </figcaption>
    </figure>
  );
}
