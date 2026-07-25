import type { TradingStrategy } from "../types/stock";

type StrategySelectorProps = {
  strategies: TradingStrategy[];
  selectedId: TradingStrategy["id"];
  onSelect: (strategyId: TradingStrategy["id"]) => void;
};

const modes: Array<{ id: TradingStrategy["id"]; label: string }> = [
  { id: "day_trading", label: "Day Trading" },
  { id: "swing_trading", label: "Swing Trading" },
  { id: "long_term", label: "Long-Term" },
  { id: "crypto", label: "Crypto" },
];

function StrategySelector({ strategies, selectedId, onSelect }: StrategySelectorProps) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <p className="text-sm font-medium text-cyan-300">Trading strategy</p>
          <p className="mt-1 text-xs text-slate-500">Choose the trading style used by the scanner.</p>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4" role="group" aria-label="Trading strategy">
          {modes.map((mode) => {
            const strategy = strategies.find((item) => item.id === mode.id);
            const status = strategy?.status ?? (mode.id === "swing_trading" ? "FORWARD_VALIDATION" : "COMING_SOON");
            const selected = selectedId === mode.id;
            return (
              <button
                key={mode.id}
                type="button"
                onClick={() => onSelect(mode.id)}
                aria-pressed={selected}
                className={`rounded-lg border px-4 py-3 text-left transition ${selected ? "border-cyan-400/50 bg-cyan-400/10 text-white" : "border-slate-800 bg-slate-950/60 text-slate-400 hover:border-slate-700 hover:text-white"}`}
              >
                <span className="block text-sm font-semibold">{mode.label}</span>
                <span className={`mt-1 block text-[11px] font-medium uppercase tracking-wide ${status === "FORWARD_VALIDATION" || status === "ACTIVE" ? "text-cyan-300" : "text-slate-600"}`}>
                  {status === "FORWARD_VALIDATION" ? "Forward validation" : status === "ACTIVE" ? "Active" : status === "DISABLED" ? "Disabled" : "Coming soon"}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export default StrategySelector;
