const navigationItems = [
  ["▦", "Dashboard"],
  ["⌁", "Scanner"],
  ["◫", "Watchlist"],
];

function Sidebar() {
  return (
    <aside className="hidden w-64 shrink-0 border-r border-slate-800 bg-slate-950 p-5 lg:flex lg:flex-col">
      <div className="mb-12 flex items-center gap-3 px-2">
        <div className="grid size-9 place-items-center rounded-lg bg-cyan-400 font-bold text-slate-950">B</div>
        <span className="font-semibold tracking-tight text-white">BEAU AI TRADER</span>
      </div>
      <nav className="space-y-1" aria-label="Primary navigation">
        {navigationItems.map(([icon, label], index) => (
          <a key={label} href="#scanner" className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${index === 0 ? "bg-cyan-400/10 text-cyan-300" : "text-slate-400 hover:bg-slate-900 hover:text-white"}`}>
            <span aria-hidden="true">{icon}</span>{label}
          </a>
        ))}
      </nav>
      <div className="mt-auto rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Scanner</p>
        <p className="mt-2 text-sm font-medium text-white">US equities</p>
        <p className="mt-1 text-xs text-slate-500">Daily technical setup</p>
      </div>
    </aside>
  );
}

export default Sidebar;
