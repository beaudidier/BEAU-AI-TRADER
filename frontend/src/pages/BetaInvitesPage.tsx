import { useEffect, useState } from "react";

import Header from "../components/Header";
import Sidebar, { type AppPage } from "../components/Sidebar";
import { userApi } from "../services/userApi";
import type { BetaInvite, CreatedBetaInvite } from "../types/database";

type BetaInvitesPageProps = {
  onNavigate: (page: AppPage) => void;
};

const statusStyles: Record<BetaInvite["status"], string> = {
  active: "border-emerald-400/20 bg-emerald-400/10 text-emerald-200",
  used: "border-slate-700 bg-slate-800 text-slate-300",
  revoked: "border-rose-400/20 bg-rose-400/10 text-rose-200",
  expired: "border-amber-400/20 bg-amber-400/10 text-amber-200",
};

export default function BetaInvitesPage({ onNavigate }: BetaInvitesPageProps) {
  const [invites, setInvites] = useState<BetaInvite[]>([]);
  const [label, setLabel] = useState("");
  const [expiresInDays, setExpiresInDays] = useState(7);
  const [maxUses, setMaxUses] = useState(1);
  const [createdInvite, setCreatedInvite] = useState<CreatedBetaInvite | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);

  async function loadInvites() {
    setLoading(true);
    setError(null);
    try {
      setInvites(await userApi.betaInvites() as BetaInvite[]);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Beta invites could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadInvites();
  }, []);

  async function createInvite(event: React.FormEvent) {
    event.preventDefault();
    setCreating(true);
    setCreatedInvite(null);
    setCopyStatus(null);
    setError(null);
    try {
      const invite = await userApi.createBetaInvite({
        label: label || null,
        expires_in_days: expiresInDays,
        max_uses: maxUses,
      }) as CreatedBetaInvite;
      setCreatedInvite(invite);
      setInvites((current) => [invite, ...current]);
      setLabel("");
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "The invite could not be created.");
    } finally {
      setCreating(false);
    }
  }

  async function copyInvite() {
    if (!createdInvite) return;
    try {
      await navigator.clipboard.writeText(createdInvite.invite_url);
      setCopyStatus("Private invite URL copied.");
    } catch {
      setCopyStatus("Copy was blocked. Select the private URL manually.");
    }
  }

  async function revokeInvite(invite: BetaInvite) {
    setError(null);
    try {
      const revoked = await userApi.revokeBetaInvite(invite.id) as BetaInvite;
      setInvites((current) => current.map((item) => item.id === revoked.id ? revoked : item));
      if (createdInvite?.id === revoked.id) setCreatedInvite(null);
    } catch (revokeError) {
      setError(revokeError instanceof Error ? revokeError.message : "The invite could not be revoked.");
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 font-sans text-slate-100 lg:flex">
      <Sidebar activePage="beta-invites" onNavigate={onNavigate} />
      <div className="min-w-0 flex-1">
        <Header eyebrow="Owner administration" title="Private Beta Invites" />
        <main className="mx-auto max-w-6xl space-y-6 p-5 sm:p-8">
          <section className="rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-5">
            <p className="font-semibold text-cyan-100">Private beta access only.</p>
            <p className="mt-2 text-sm leading-6 text-slate-300">Invite tokens are shown once, stored only as secure hashes, and never included in the invite history.</p>
          </section>

          <form onSubmit={createInvite} className="rounded-2xl border border-slate-800 bg-slate-900/50 p-5 sm:p-6">
            <h2 className="text-lg font-semibold text-white">Create beta invite</h2>
            <div className="mt-5 grid gap-4 md:grid-cols-3">
              <label className="text-sm text-slate-300">Optional label<input value={label} onChange={(event) => setLabel(event.target.value)} maxLength={120} placeholder="Professional trader beta" className="mt-2 h-11 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-white placeholder:text-slate-600" /></label>
              <label className="text-sm text-slate-300">Expires in days<input type="number" min={1} max={30} value={expiresInDays} onChange={(event) => setExpiresInDays(Number(event.target.value))} className="mt-2 h-11 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-white" /></label>
              <label className="text-sm text-slate-300">Maximum uses<input type="number" min={1} max={100} value={maxUses} onChange={(event) => setMaxUses(Number(event.target.value))} className="mt-2 h-11 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-white" /></label>
            </div>
            <button disabled={creating} className="mt-5 rounded-lg bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 disabled:opacity-60">{creating ? "Creating…" : "Create beta invite"}</button>
          </form>

          {createdInvite && (
            <section className="rounded-2xl border border-emerald-400/20 bg-emerald-400/10 p-5">
              <h2 className="font-semibold text-emerald-100">Private invite created</h2>
              <p className="mt-2 text-sm text-emerald-100/80">Copy this URL now. It will not be shown again after this page is closed.</p>
              <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                <input readOnly value={createdInvite.invite_url} aria-label="Private invite URL" className="h-11 min-w-0 flex-1 rounded-lg border border-emerald-400/20 bg-slate-950 px-3 text-sm text-slate-200" />
                <button type="button" onClick={copyInvite} className="rounded-lg bg-emerald-400 px-5 py-3 text-sm font-semibold text-slate-950">Copy private URL</button>
              </div>
              <p className="mt-3 text-xs text-emerald-100/70">Expires {new Date(createdInvite.expires_at).toLocaleString()} · {createdInvite.remaining_uses} use remaining</p>
              {copyStatus && <p className="mt-3 text-sm text-emerald-100">{copyStatus}</p>}
            </section>
          )}

          {error && <p className="rounded-lg border border-rose-400/20 bg-rose-400/10 p-4 text-sm text-rose-200">{error}</p>}

          <section className="rounded-2xl border border-slate-800 bg-slate-900/50 p-5 sm:p-6">
            <h2 className="text-lg font-semibold text-white">Invite history</h2>
            {loading ? <p className="mt-4 text-sm text-slate-400">Loading private invites…</p> : invites.length === 0 ? <p className="mt-4 text-sm text-slate-500">No private invites have been created.</p> : (
              <div className="mt-4 space-y-3">
                {invites.map((invite) => (
                  <article key={invite.id} className="flex flex-col gap-4 rounded-xl border border-slate-800 bg-slate-950/60 p-4 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-semibold text-white">{invite.label || "Unlabelled beta invite"}</p>
                        <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold uppercase ${statusStyles[invite.status]}`}>{invite.status}</span>
                      </div>
                      <p className="mt-2 text-xs text-slate-500">Expires {new Date(invite.expires_at).toLocaleString()} · {invite.remaining_uses} of {invite.max_uses} uses remaining</p>
                    </div>
                    {invite.status === "active" && <button type="button" onClick={() => void revokeInvite(invite)} className="rounded-lg border border-rose-400/30 px-4 py-2 text-sm font-semibold text-rose-200 hover:bg-rose-400/10">Revoke</button>}
                  </article>
                ))}
              </div>
            )}
          </section>
        </main>
      </div>
    </div>
  );
}
