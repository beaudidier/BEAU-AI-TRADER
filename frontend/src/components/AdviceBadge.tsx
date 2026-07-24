type AdviceBadgeProps = {
  advice: string;
};

function AdviceBadge({ advice }: AdviceBadgeProps) {
  const colorClass = advice.includes("BUY")
    ? "bg-emerald-400/10 text-emerald-300 ring-emerald-400/20"
    : advice.includes("WATCH")
      ? "bg-amber-400/10 text-amber-300 ring-amber-400/20"
      : "bg-rose-400/10 text-rose-300 ring-rose-400/20";

  const label = advice.replaceAll("🟢", "").replaceAll("🟡", "").replaceAll("🔴", "").trim();

  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${colorClass}`}>{label}</span>;
}

export default AdviceBadge;
