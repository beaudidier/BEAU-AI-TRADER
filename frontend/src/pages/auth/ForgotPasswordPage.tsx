import { useState } from "react";
import { Link } from "react-router-dom";

import { AuthInput } from "../../components/auth/AuthInput";
import { AuthShell } from "../../components/auth/AuthShell";
import { supabase } from "../../lib/supabase";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!supabase || loading) {
      if (!supabase) {
        setError("Password recovery is temporarily unavailable.");
      }
      return;
    }
    setLoading(true);
    setError(null);
    const { error: authError } = await supabase.auth.resetPasswordForEmail(
      email,
      { redirectTo: `${window.location.origin}/reset-password` },
    );
    setLoading(false);
    if (
      authError?.status === 429
      || authError?.code === "over_email_send_rate_limit"
      || authError?.code === "over_request_rate_limit"
    ) {
      setError(
        "Too many recovery emails were requested. Please wait a minute and try again.",
      );
      return;
    }
    if (authError) {
      setError(
        "Password recovery could not be started right now. Please try again later.",
      );
      return;
    }
    setMessage(
      "Password reset instructions were sent if this email is registered. Check your inbox and spam folder.",
    );
  }

  return (
    <AuthShell title="Reset your password">
      <form onSubmit={submit} className="space-y-5">
        <AuthInput label="Email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        {error && <p className="text-sm text-rose-200">{error}</p>}
        {message && <p className="text-sm text-emerald-200">{message}</p>}
        <button disabled={loading || Boolean(message)} className="h-11 w-full rounded-lg bg-cyan-400 font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-60">
          {loading ? "Sending secure email…" : message ? "Email requested" : "Send reset email"}
        </button>
      </form>
      <Link to="/login" className="mt-6 inline-block text-sm text-cyan-300">
        Back to sign in
      </Link>
    </AuthShell>
  );
}
