import { useEffect, useState } from "react";

import { userApi } from "../services/userApi";

type Watchlist = { id: string; name: string; watchlist_items: Array<{ ticker: string }> };

export function WatchlistManager() {
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]); const [name, setName] = useState(""); const [error, setError] = useState<string | null>(null); const [loading, setLoading] = useState(true);
  async function load() { try { setWatchlists(await userApi.watchlists()); } catch (loadError) { setError(loadError instanceof Error ? loadError.message : "Unable to load watchlists."); } finally { setLoading(false); } }
  useEffect(() => { void load(); }, []);
  async function create(event: React.FormEvent) { event.preventDefault(); try { await userApi.createWatchlist(name); setName(""); await load(); } catch (createError) { setError(createError instanceof Error ? createError.message : "Unable to create watchlist."); } }
  if (loading) return <p className="text-sm text-slate-500">Loading watchlists…</p>;
  return <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-5"><h2 className="font-semibold text-white">Watchlists</h2><form onSubmit={create} className="mt-4 flex gap-2"><input value={name} onChange={(event) => setName(event.target.value)} placeholder="New watchlist" className="h-10 min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm text-white" required /><button className="rounded-lg bg-cyan-400 px-3 text-sm font-semibold text-slate-950">Create</button></form>{error && <p className="mt-3 text-sm text-rose-200">{error}</p>}<ul className="mt-4 space-y-2">{watchlists.map((watchlist) => <li key={watchlist.id} className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-slate-300"><span className="font-medium text-white">{watchlist.name}</span><span className="ml-2 text-slate-500">{watchlist.watchlist_items.map((item) => item.ticker).join(", ") || "No tickers"}</span></li>)}{watchlists.length === 0 && <li className="text-sm text-slate-500">No watchlists yet.</li>}</ul></section>;
}
