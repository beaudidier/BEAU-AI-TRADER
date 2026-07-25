import { Link } from "react-router-dom";

import type { LatestSignalEvidence } from "../types/latestSignals";
import LatestSignalChart from "./LatestSignalChart";

type LatestSignalCardProps = {
  signal: LatestSignalEvidence;
};

function price(value: number) {
  return `$${value.toFixed(4)}`;
}

export default function LatestSignalCard({ signal }: LatestSignalCardProps) {
  const values = [
    ["Signal price", price(signal.signal_price)],
    ["EMA20", price(signal.levels.ema20)],
    ["EMA50", price(signal.levels.ema50)],
    ["Pullback entry", price(signal.levels.pullback_entry)],
    ["Swing low", price(signal.levels.swing_low)],
    ["Stop", price(signal.levels.stop)],
    ["TP1", price(signal.levels.tp1)],
    ["TP2", price(signal.levels.tp2)],
  ];

  return (
    <article className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/50">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-800 p-5">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2.5 py-1 text-xs font-semibold text-emerald-200">VALID REPLAY SIGNAL</span>
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{signal.signal_date}</span>
          </div>
          <h2 className="mt-3 text-2xl font-semibold text-white">{signal.ticker}</h2>
          <p className="mt-1 text-sm text-slate-400">{signal.company_name} · {signal.sector}</p>
        </div>
        <Link to={`/workspace/${encodeURIComponent(signal.ticker)}`} className="rounded-lg bg-cyan-400 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300">
          Open workspace
        </Link>
      </div>

      <div className="grid gap-5 p-5 2xl:grid-cols-[minmax(0,1.45fr)_minmax(22rem,0.75fr)]">
        <LatestSignalChart signal={signal} />
        <div className="space-y-4">
          <dl className="grid grid-cols-2 gap-2">
            {values.map(([label, value]) => (
              <div key={label} className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
                <dd className="mt-1 font-mono text-sm font-semibold text-slate-100">{value}</dd>
              </div>
            ))}
          </dl>
          <dl className="grid gap-2 sm:grid-cols-2">
            <div className="rounded-lg bg-slate-950/60 p-3">
              <dt className="text-xs text-slate-500">Confidence</dt>
              <dd className="mt-1 text-lg font-semibold text-white">{signal.confidence.toFixed(0)}</dd>
            </div>
            <div className="rounded-lg bg-slate-950/60 p-3">
              <dt className="text-xs text-slate-500">Risk percentage</dt>
              <dd className="mt-1 text-lg font-semibold text-white">{signal.risk_percent.toFixed(2)}%</dd>
            </div>
            <div className="rounded-lg bg-slate-950/60 p-3">
              <dt className="text-xs text-slate-500">Risk / reward</dt>
              <dd className="mt-1 text-sm font-semibold text-white">{signal.risk_reward_target_1.toFixed(1)}R / {signal.risk_reward_target_2.toFixed(1)}R</dd>
            </div>
            <div className="rounded-lg bg-slate-950/60 p-3">
              <dt className="text-xs text-slate-500">Market regime</dt>
              <dd className="mt-1 text-sm font-semibold text-white">Score {signal.market_regime_score.toFixed(0)}</dd>
            </div>
          </dl>
          <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Market-regime explanation</p>
            <p className="mt-2 text-sm leading-6 text-slate-300">{signal.market_regime}</p>
          </div>
        </div>
      </div>

      <div className="border-t border-slate-800 p-5">
        <h3 className="text-sm font-semibold text-emerald-200">Exact qualification reasons</h3>
        <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-400">
          {signal.qualification_reasons.map((reason) => <li key={reason}>• {reason}</li>)}
        </ul>
        <p className="mt-4 text-xs text-slate-600">Frozen strategy version: {signal.strategy_version} · Data timestamp: {signal.data_timestamp}</p>
      </div>
    </article>
  );
}
