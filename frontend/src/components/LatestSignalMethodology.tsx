import type { LatestSignalEvidenceSummary } from "../types/latestSignals";

type LatestSignalMethodologyProps = {
  summary: LatestSignalEvidenceSummary;
};

export default function LatestSignalMethodology({ summary }: LatestSignalMethodologyProps) {
  return (
    <section className="rounded-xl border border-amber-400/25 bg-amber-400/10 p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-amber-300">Methodology and limitations</p>
      <h2 className="mt-2 text-lg font-semibold text-white">Replay evidence—not a live-money recommendation</h2>
      <ul className="mt-3 space-y-2 text-sm leading-6 text-amber-100/80">
        <li>• These signals come from the latest complete S&amp;P 500 production-path replay.</li>
        <li>• Every calculation uses completed daily candles available at the signal timestamp; no look-ahead data is used.</li>
        <li>• The evidence uses frozen strategy version {summary.strategy.version} without changing its entry, stop, target, regime, risk, or scoring rules.</li>
        <li>• Forward validation and paper trading only. Historical replay signals do not guarantee entry, profit, or future performance.</li>
      </ul>
    </section>
  );
}
