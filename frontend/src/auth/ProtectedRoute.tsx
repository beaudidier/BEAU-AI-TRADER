import { Navigate } from "react-router-dom";

import { useAuth } from "../hooks/useAuth";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="grid min-h-screen place-items-center bg-slate-950 text-sm text-slate-400">Loading your session…</div>;
  return user ? <>{children}</> : <Navigate to="/login" replace />;
}

export function GuestRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="grid min-h-screen place-items-center bg-slate-950 text-sm text-slate-400">Loading your session…</div>;
  return user ? <Navigate to="/dashboard" replace /> : <>{children}</>;
}
