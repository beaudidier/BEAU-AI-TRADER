import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AuthInput } from "../../components/auth/AuthInput";
import { AuthShell } from "../../components/auth/AuthShell";
import { supabase } from "../../lib/supabase";

export default function ResetPasswordPage() { const navigate = useNavigate(); const [password, setPassword] = useState(""); const [error, setError] = useState<string | null>(null); async function submit(event: React.FormEvent) { event.preventDefault(); if (!supabase) return setError("Supabase is not configured."); const { error: authError } = await supabase.auth.updateUser({ password }); if (authError) setError(authError.message); else navigate("/dashboard"); } return <AuthShell title="Choose a new password"><form onSubmit={submit} className="space-y-5"><AuthInput label="New password" type="password" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} required />{error && <p className="text-sm text-rose-200">{error}</p>}<button className="h-11 w-full rounded-lg bg-cyan-400 font-semibold text-slate-950">Update password</button></form></AuthShell>; }
