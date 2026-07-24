type ScoreBadgeProps = {
  score: number;
};

function ScoreBadge({ score }: ScoreBadgeProps) {
  const colorClass = score >= 70
    ? "bg-emerald-400/10 text-emerald-300 ring-emerald-400/20"
    : score >= 55
      ? "bg-amber-400/10 text-amber-300 ring-amber-400/20"
      : "bg-slate-700 text-slate-300 ring-slate-600";

  return <span className={`inline-flex min-w-11 justify-center rounded-md px-2 py-1 font-mono text-xs font-semibold ring-1 ${colorClass}`}>{score}</span>;
}

export default ScoreBadge;
