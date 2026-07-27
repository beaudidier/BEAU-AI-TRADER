import { useEffect, useState } from "react";

import { getMarketDataTransparency } from "../services/api";
import type {
  MarketDataLabel,
  MarketDataTransparency,
} from "../types/stock";

type MarketDataTransparencyPanelProps = {
  ticker: string;
};

const sessionTone = {
  premarket: "border-sky-400/30 bg-sky-400/10 text-sky-200",
  open: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  "after-hours": "border-violet-400/30 bg-violet-400/10 text-violet-200",
  closed: "border-slate-600 bg-slate-800/70 text-slate-300",
};

const dataTone: Record<MarketDataLabel, string> = {
  live: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  delayed: "border-amber-400/30 bg-amber-400/10 text-amber-200",
  unknown: "border-slate-600 bg-slate-800/70 text-slate-300",
};

function timestamp(value: string | null): string {
  if (!value) return "Timestamp unavailable";
  return new Date(value).toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function label(value: string): string {
  return value.replace("-", " ").replace(/\b\w/g, (character) => (
    character.toUpperCase()
  ));
}

function DataLabel({ value }: { value: MarketDataLabel }) {
  return (
    <span className={`rounded-full border px-2 py-1 text-[0.65rem] font-semibold uppercase tracking-wider ${dataTone[value]}`}>
      {value}
    </span>
  );
}

function MarketDataTransparencyPanel({
  ticker,
}: MarketDataTransparencyPanelProps) {
  const [data, setData] = useState<MarketDataTransparency | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void getMarketDataTransparency(ticker)
      .then((result) => {
        if (active) setData(result);
      })
      .catch((loadError: unknown) => {
        if (active) {
          setError(loadError instanceof Error
            ? loadError.message
            : "Market-data timing details are temporarily unavailable.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [attempt, ticker]);

  if (loading && !data) {
    return (
      <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
        <p className="text-sm text-slate-400">Checking market-data timing…</p>
      </section>
    );
  }

  if (error && !data) {
    return (
      <section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-400/20 bg-amber-400/10 p-4">
        <p className="text-sm text-amber-100">{error}</p>
        <button
          type="button"
          onClick={() => setAttempt((value) => value + 1)}
          className="rounded-lg border border-amber-300/40 px-3 py-2 text-xs font-semibold text-amber-100 transition hover:bg-amber-300/10"
        >
          Retry timing check
        </button>
      </section>
    );
  }

  if (!data) return null;

  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 shadow-lg shadow-slate-950/20">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-300">
            Market data transparency
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Provider: {data.provider} · Times shown in your local timezone
          </p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wider ${sessionTone[data.market_status]}`}>
          Market {label(data.market_status)}
        </span>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <article className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Indicative current quote
            </p>
            <DataLabel value={data.current_quote.data_label} />
          </div>
          <p className="mt-3 text-2xl font-semibold tabular-nums text-white">
            {data.current_quote.price === null
              ? "Unavailable"
              : `$${data.current_quote.price.toFixed(2)}`}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Last price update: {timestamp(data.current_quote.last_price_update_timestamp)}
          </p>
          <p className="mt-3 text-xs leading-5 text-slate-400">
            Indicative only. This price is not used to rewrite the validated daily signal.
          </p>
        </article>

        <article className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Validated daily signal
            </p>
            <DataLabel value={data.validated_daily_signal.data_label} />
          </div>
          <p className="mt-3 text-base font-semibold text-white">
            Latest completed candle
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {timestamp(data.validated_daily_signal.latest_completed_candle_timestamp)}
          </p>
          <p className="mt-3 text-xs leading-5 text-slate-400">
            Scores and trade-plan levels remain tied to this completed daily candle.
          </p>
        </article>
      </div>

      {data.stale_data_warning && (
        <div className="mt-3 rounded-lg border border-amber-400/30 bg-amber-400/10 p-3 text-sm leading-5 text-amber-100">
          <span className="font-semibold">Stale-data warning:</span>{" "}
          {data.stale_data_warning}
        </div>
      )}

      {error && (
        <p className="mt-3 text-xs text-amber-200">
          Refresh failed; the previous timing details remain visible.
        </p>
      )}
    </section>
  );
}

export default MarketDataTransparencyPanel;
