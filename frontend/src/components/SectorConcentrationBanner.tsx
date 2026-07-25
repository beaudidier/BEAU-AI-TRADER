import type { SectorConcentration } from "../types/setupClarity";

type SectorConcentrationBannerProps = {
  concentration: SectorConcentration;
};

export default function SectorConcentrationBanner({ concentration }: SectorConcentrationBannerProps) {
  return (
    <section className={`rounded-xl border p-5 ${concentration.has_warning ? "border-amber-400/30 bg-amber-400/10" : "border-emerald-400/20 bg-emerald-400/10"}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className={`text-xs font-semibold uppercase tracking-wide ${concentration.has_warning ? "text-amber-300" : "text-emerald-300"}`}>Sector concentration</p>
          <h2 className="mt-2 text-lg font-semibold text-white">
            {concentration.has_warning ? "Active setups share meaningful market risk" : "Active setups are diversified across sectors"}
          </h2>
          <p className="mt-1 text-sm text-slate-400">{concentration.active_signal_count} active setup{concentration.active_signal_count === 1 ? "" : "s"} included.</p>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${concentration.has_warning ? "bg-amber-300 text-amber-950" : "bg-emerald-300 text-emerald-950"}`}>
          {concentration.has_warning ? "CONCENTRATION WARNING" : "NO CONCENTRATION WARNING"}
        </span>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
        {concentration.sectors.map((item) => (
          <div key={item.sector} className="rounded-lg border border-white/10 bg-slate-950/40 p-3">
            <p className="text-xs text-slate-400">{item.sector}</p>
            <p className="mt-1 font-semibold text-white">{item.count} · {item.percentage.toFixed(1)}%</p>
          </div>
        ))}
      </div>

      {concentration.warnings.length > 0 && (
        <ul className="mt-4 space-y-2 text-sm leading-6 text-amber-100">
          {concentration.warnings.map((warning) => <li key={warning}>• {warning}</li>)}
        </ul>
      )}
    </section>
  );
}
