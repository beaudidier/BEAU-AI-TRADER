type HeaderProps = {
  eyebrow?: string;
  title?: string;
};

function Header({ eyebrow = "Market overview", title = "Scanner Dashboard" }: HeaderProps) {
  return (
    <header className="flex h-20 items-center justify-between border-b border-slate-800 bg-slate-950 px-5 sm:px-8">
      <div>
        <p className="text-sm font-medium text-slate-400">{eyebrow}</p>
        <h1 className="text-xl font-semibold tracking-tight text-white sm:text-2xl">{title}</h1>
      </div>
      <div className="flex items-center gap-3">
        <span className="hidden text-sm text-slate-400 sm:block">Live market scanner</span>
        <div className="grid size-10 place-items-center rounded-full bg-cyan-500/15 font-semibold text-cyan-300 ring-1 ring-cyan-400/30">BD</div>
      </div>
    </header>
  );
}

export default Header;
