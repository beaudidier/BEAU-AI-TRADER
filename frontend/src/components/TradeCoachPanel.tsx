import { useEffect, useState } from "react";

import { analyzeTradeCoach } from "../services/api";
import type { BacktestTrade, CoachAnalysis } from "../types/stock";
import ExplainableRecommendation from "./ExplainableRecommendation";

type TradeCoachPanelProps = {
  trade: BacktestTrade;
};

function AdviceList({ title, items, tone }: { title: string; items: string[]; tone: "positive" | "warning" | "neutral" }) {
  const toneClasses = {
    positive: "border-emerald-400/20 bg-emerald-400/5 text-emerald-100",
    warning: "border-rose-400/20 bg-rose-400/5 text-rose-100",
    neutral: "border-cyan-400/20 bg-cyan-400/5 text-cyan-100",
  };

  return <div className={`rounded-xl border p-4 ${toneClasses[tone]}`}><h4 className="text-sm font-semibold">{title}</h4>{items.length > 0 ? <ul className="mt-3 space-y-2 text-sm leading-6"><li>{items[0]}</li>{items.slice(1).map((item) => <li key={item}>{item}</li>)}</ul> : <p className="mt-3 text-sm leading-6 opacity-80">No issues identified from the recorded trade data.</p>}</div>;
}

function TradeCoachPanel({ trade }: TradeCoachPanelProps) {
  const [analysis, setAnalysis] = useState<CoachAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    analyzeTradeCoach(trade).then((result) => {
      if (active) setAnalysis(result);
    }).catch((loadError: unknown) => {
      if (active) setError(loadError instanceof Error ? loadError.message : "Unable to load AI Coach feedback.");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [trade]);

  if (loading) return <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6 text-sm text-slate-400">Preparing deterministic trade review…</div>;
  if (error) return <div className="rounded-xl border border-rose-400/20 bg-rose-400/10 p-6 text-sm text-rose-200">{error}</div>;
  if (!analysis) return null;

  return <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-300">AI Coach</p><h3 className="mt-1 text-lg font-semibold text-white">{trade.ticker} completed trade review</h3><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">{analysis.summary}</p></div><div className="flex gap-3"><div className="rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-center"><p className="text-xs uppercase tracking-wide text-cyan-200">Grade</p><p className="mt-1 text-2xl font-bold text-cyan-300">{analysis.grade}</p></div><div className="rounded-lg border border-slate-700 bg-slate-950 px-4 py-2 text-center"><p className="text-xs uppercase tracking-wide text-slate-500">Discipline</p><p className="mt-1 text-2xl font-bold text-white">{analysis.discipline_score}</p></div></div></div><div className="mt-5 grid gap-3 lg:grid-cols-3"><AdviceList title="Done well" items={analysis.positives} tone="positive" /><AdviceList title="Mistakes" items={analysis.mistakes} tone="warning" /><AdviceList title="Improve next time" items={analysis.improvements} tone="neutral" /></div><div className="mt-4 grid gap-3 md:grid-cols-2"><div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4"><p className="text-xs font-medium uppercase tracking-wide text-slate-500">Confidence alignment</p><p className="mt-2 text-sm leading-6 text-slate-300">{analysis.confidence_alignment}</p></div><div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4"><p className="text-xs font-medium uppercase tracking-wide text-slate-500">Emotional bias</p><p className="mt-2 text-sm leading-6 text-slate-300">{analysis.emotional_bias}</p></div></div><ExplainableRecommendation explanation={analysis.explanation} /></div>;
}

export default TradeCoachPanel;
