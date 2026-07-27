import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { AuthInput } from "../../components/auth/AuthInput";
import { AuthShell } from "../../components/auth/AuthShell";
import { supabase } from "../../lib/supabase";

export default function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const sessionExpired = searchParams.get("reason") === "session-expired";

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!supabase) {
      setError("Sign in is temporarily unavailable. Please try again later.");
      return;
    }
    setLoading(true);
    setError(null);
    const { error: authError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    setLoading(false);
    if (!authError) {
      navigate("/dashboard");
      return;
    }
    if (authError.code === "email_not_confirmed") {
      setError(
        "Your email is not verified yet. Open the verification email, or reopen your private invite to request another one.",
      );
    } else if (
      authError.code === "over_request_rate_limit"
      || authError.code === "over_email_send_rate_limit"
      || authError.status === 429
    ) {
      setError(
        "Too many sign-in attempts were made. Please wait a minute and try again.",
      );
    } else {
      setError("The email or password is incorrect. Please try again.");
    }
  }

  return (
    <AuthShell title="Private beta sign in">
      <p className="mb-5 rounded-lg border border-cyan-400/20 bg-cyan-400/10 p-3 text-sm leading-5 text-cyan-100">
        Invite-only access for the owner and approved professional tester.
      </p>
      {sessionExpired && (
        <p className="mb-5 rounded-lg border border-amber-400/20 bg-amber-400/10 p-3 text-sm leading-5 text-amber-100">
          Your session expired safely. Sign in again to continue where you left off.
        </p>
      )}
      <form onSubmit={submit} className="space-y-5">
        <AuthInput label="Email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        <AuthInput label="Password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        {error && <p className="rounded-lg bg-rose-400/10 p-3 text-sm text-rose-200">{error}</p>}
        <button disabled={loading} className="h-11 w-full rounded-lg bg-cyan-400 font-semibold text-slate-950 disabled:opacity-70">
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <div className="mt-6 text-sm text-slate-400">
        <Link to="/forgot-password" className="hover:text-cyan-300">Forgot password?</Link>
      </div>
    </AuthShell>
  );
}
