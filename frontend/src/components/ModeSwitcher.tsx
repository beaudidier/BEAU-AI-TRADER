import { useExperienceMode } from "../contexts/ExperienceModeContext";

export default function ModeSwitcher() {
  const { mode, setMode, saving, error } = useExperienceMode();
  return <div>
    <div className="inline-flex rounded-xl border border-slate-700 bg-slate-950 p-1" role="group" aria-label="Experience mode">
      {(["beginner", "advanced"] as const).map((value) => <button key={value} type="button" aria-pressed={mode === value} disabled={saving} onClick={() => void setMode(value)} className={`rounded-lg px-4 py-2 text-sm font-semibold capitalize outline-none transition focus-visible:ring-2 focus-visible:ring-cyan-300 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 ${mode === value ? "bg-cyan-300 text-slate-950" : "text-slate-300 hover:bg-slate-800 hover:text-white"}`}>{value}</button>)}
    </div>
    {error && <p className="mt-2 text-xs text-rose-200" role="alert">{error}</p>}
  </div>;
}
