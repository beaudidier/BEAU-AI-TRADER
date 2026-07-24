import type { Timeframe } from "../types/stock";

const timeframes: Timeframe[] = ["1D", "1W", "1M", "3M", "6M", "1Y"];

type TimeframeSelectorProps = {
  value: Timeframe;
  onChange: (timeframe: Timeframe) => void;
};

function TimeframeSelector({ value, onChange }: TimeframeSelectorProps) {
  return (
    <div className="flex rounded-lg border border-slate-700 bg-slate-950 p-1" aria-label="Chart timeframe">
      {timeframes.map((timeframe) => (
        <button key={timeframe} type="button" onClick={() => onChange(timeframe)} className={`rounded-md px-2.5 py-1.5 text-xs font-semibold transition sm:px-3 ${timeframe === value ? "bg-cyan-400 text-slate-950" : "text-slate-400 hover:text-white"}`}>
          {timeframe}
        </button>
      ))}
    </div>
  );
}

export default TimeframeSelector;
