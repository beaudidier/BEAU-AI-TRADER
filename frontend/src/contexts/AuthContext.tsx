import type { Session } from "@supabase/supabase-js";
import { useEffect, useMemo, useState } from "react";

import { AuthContext } from "./AuthContextValue";
import { supabase } from "../lib/supabase";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!supabase) { setLoading(false); return undefined; }
    void supabase.auth.getSession().then(({ data }) => { setSession(data.session); setLoading(false); });
    const { data: subscription } = supabase.auth.onAuthStateChange((_event, nextSession) => { setSession(nextSession); setLoading(false); });
    return () => subscription.subscription.unsubscribe();
  }, []);

  const value = useMemo(() => ({ user: session?.user ?? null, session, loading, configured: Boolean(supabase), signOut: async () => { if (supabase) await supabase.auth.signOut(); } }), [loading, session]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
