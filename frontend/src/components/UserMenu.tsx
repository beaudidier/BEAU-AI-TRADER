import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../hooks/useAuth";

export function UserMenu() {
  const { user, signOut } = useAuth(); const navigate = useNavigate();
  async function logout() { await signOut(); navigate("/login"); }
  return <div className="flex items-center gap-3"><Link to="/settings/profile" className="hidden text-sm text-slate-400 hover:text-white sm:block">Profile</Link><Link to="/settings/billing" className="hidden text-sm text-slate-400 hover:text-white sm:block">Billing</Link><span className="grid size-9 place-items-center rounded-full bg-cyan-500/15 text-sm font-semibold text-cyan-300">{user?.email?.slice(0, 2).toUpperCase() ?? "U"}</span><button onClick={logout} className="text-sm font-medium text-slate-400 hover:text-white">Logout</button></div>;
}
