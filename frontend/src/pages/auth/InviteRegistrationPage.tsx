import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { AuthInput } from "../../components/auth/AuthInput";
import { AuthShell } from "../../components/auth/AuthShell";
import { registerWithInvite } from "../../services/inviteRegistration";

export default function InviteRegistrationPage() {
  const { token: routeToken = "" } = useParams();
  const [inviteToken] = useState(routeToken);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (routeToken) {
      window.history.replaceState(window.history.state, "", "/invite");
    }
  }, [routeToken]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    if (!inviteToken) {
      setError("This private beta invite is invalid.");
      return;
    }
    if (password !== confirmPassword) {
      setError("The passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      const result = await registerWithInvite({
        token: inviteToken,
        email,
        password,
      });
      setMessage(result.message ?? "Check your email to verify your account before signing in.");
      setPassword("");
      setConfirmPassword("");
    } catch (registrationError) {
      setError(registrationError instanceof Error ? registrationError.message : "Private beta registration could not be completed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell title="Create your private beta account">
      <p className="mb-5 rounded-lg border border-cyan-400/20 bg-cyan-400/10 p-3 text-sm font-medium text-cyan-100">
        Private beta access only.
      </p>
      {message ? (
        <div className="space-y-5">
          <p className="rounded-lg border border-emerald-400/20 bg-emerald-400/10 p-4 text-sm leading-6 text-emerald-100">{message}</p>
          <p className="text-sm leading-6 text-slate-400">Email verification remains required. You cannot sign in until the confirmation link has been opened.</p>
          <Link to="/login" className="inline-flex h-11 w-full items-center justify-center rounded-lg bg-cyan-400 font-semibold text-slate-950">Go to sign in</Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-5">
          <AuthInput label="Email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          <AuthInput label="Password" type="password" minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} required />
          <AuthInput label="Confirm password" type="password" minLength={12} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required />
          <p className="text-xs leading-5 text-slate-500">Use at least 12 characters with upper-case, lower-case, and numeric characters.</p>
          {error && <p className="rounded-lg border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-200">{error}</p>}
          <button disabled={loading} className="h-11 w-full rounded-lg bg-cyan-400 font-semibold text-slate-950 disabled:opacity-60">{loading ? "Creating secure account…" : "Create private beta account"}</button>
        </form>
      )}
      <Link to="/login" className="mt-6 inline-flex text-sm text-cyan-300 hover:text-cyan-200">Already registered? Sign in</Link>
    </AuthShell>
  );
}
