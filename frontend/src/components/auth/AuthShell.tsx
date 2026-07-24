export function AuthShell({ title, children }: { title: string; children: React.ReactNode }) {
  return <main className="grid min-h-screen place-items-center bg-slate-950 p-5"><section className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900/50 p-7 shadow-2xl shadow-slate-950/40"><div className="mb-8"><p className="text-sm font-semibold text-cyan-300">BEAU AI TRADER</p><h1 className="mt-2 text-2xl font-semibold text-white">{title}</h1></div>{children}</section></main>;
}
