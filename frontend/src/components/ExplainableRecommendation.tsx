import type { ExplainableRecommendation as Explanation } from "../types/stock";

function ExplanationList({ title, items, tone }: { title: string; items: string[]; tone: "positive" | "warning" | "risk" }) {
  const tones = { positive: "border-emerald-400/20 bg-emerald-400/5 text-emerald-100", warning: "border-amber-400/20 bg-amber-400/5 text-amber-100", risk: "border-rose-400/20 bg-rose-400/5 text-rose-100" };
  return <div className={`rounded-lg border p-3 ${tones[tone]}`}><p className="text-xs font-semibold uppercase tracking-wide">{title}</p><ul className="mt-2 space-y-2 text-xs leading-5">{items.map((item) => <li key={item}>{item}</li>)}</ul></div>;
}

function ExplainableRecommendation({ explanation, compact = false }: { explanation: Explanation; compact?: boolean }) {
  if (compact) return <p className="mt-3 text-xs leading-5 text-slate-400">{explanation.summary}</p>;
  return <section className="mt-5 border-t border-slate-800 pt-5"><p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-300">Why this decision</p><p className="mt-2 text-sm leading-6 text-slate-300">{explanation.summary}</p><div className="mt-4 grid gap-3 lg:grid-cols-3"><ExplanationList title="Strengths" items={explanation.strengths} tone="positive" /><ExplanationList title="Almost failed" items={explanation.weaknesses} tone="warning" /><ExplanationList title="Biggest risk" items={explanation.risks} tone="risk" /></div><div className="mt-3 grid gap-3 md:grid-cols-2"><div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">What improves confidence</p><p className="mt-2 text-xs leading-5 text-slate-300">{explanation.next_trigger}</p></div><div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Invalidation</p><p className="mt-2 text-xs leading-5 text-slate-300">{explanation.invalidation}</p></div></div><p className="mt-3 text-xs text-slate-500">{explanation.confidence_explanation}</p></section>;
}

export default ExplainableRecommendation;
