import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { AuthInput } from "../../components/auth/AuthInput";
import { AuthShell } from "../../components/auth/AuthShell";
import { supabase } from "../../lib/supabase";

export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
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
    const { error: authError } = await supabase.auth.updateUser({ password });
    setLoading(false);
    if (!authError) {
      navigate("/dashboard");
      return;
    }
    if (authError.code === "weak_password") {
      setError(
        "Choose at least 12 characters with upper-case, lower-case, and numeric characters.",
      );
    } else if (
      authError.code === "session_expired"
      || authError.code === "session_not_found"
    ) {
      setError(
        "This recovery link has expired. Return to sign in and request a new password-reset email.",
      );
    } else {
      setError("Your password could not be updated. Please request a new recovery email.");
    }
  }

  return (
    <AuthShell title="Choose a new password">
      <form onSubmit={submit} className="space-y-5">
        <AuthInput label="New password" type="password" minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} required />
        <p className="text-xs leading-5 text-slate-500">
          Use at least 12 characters with upper-case, lower-case, and numeric characters.
        </p>
        {error && <p className="text-sm text-rose-200">{error}</p>}
        <button disabled={loading} className="h-11 w-full rounded-lg bg-cyan-400 font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-60">
          {loading ? "Updating password…" : "Update password"}
        </button>
      </form>
    </AuthShell>
  );
}
