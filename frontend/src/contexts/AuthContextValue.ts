import { createContext } from "react";
import type { Session, User } from "@supabase/supabase-js";

export type AuthContextValue = { user: User | null; session: Session | null; loading: boolean; configured: boolean; signOut: () => Promise<void> };
export const AuthContext = createContext<AuthContextValue | undefined>(undefined);
