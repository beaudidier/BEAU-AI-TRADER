type HeaderProps = {
  eyebrow?: string;
  title?: string;
};

import { UserMenu } from "./UserMenu";

function Header({ eyebrow = "Market overview", title = "Scanner Dashboard" }: HeaderProps) {
  return (
    <header className="flex h-20 items-center justify-between border-b border-slate-800 bg-slate-950 px-5 sm:px-8">
      <div>
        <p className="text-sm font-medium text-slate-400">{eyebrow}</p>
        <h1 className="text-xl font-semibold tracking-tight text-white sm:text-2xl">{title}</h1>
      </div>
      <UserMenu />
    </header>
  );
}

export default Header;
