import { createContext, useContext, useEffect, useMemo, useState } from "react";

/* oxlint-disable react/only-export-components -- Provider and its scoped hook form one context API. */

import { loadExperienceMode, saveExperienceMode, type ExperienceMode } from "../services/experienceMode";
import { useAuth } from "../hooks/useAuth";

type ExperienceModeValue = {
  mode: ExperienceMode;
  loading: boolean;
  saving: boolean;
  error: string | null;
  setMode: (mode: ExperienceMode) => Promise<void>;
};

const ExperienceModeContext = createContext<ExperienceModeValue | null>(null);

export function ExperienceModeProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [mode, setModeState] = useState<ExperienceMode>("advanced");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!user) {
      setModeState("advanced");
      setLoading(false);
      return () => { active = false; };
    }
    setLoading(true);
    void loadExperienceMode()
      .then((value) => { if (active) setModeState(value); })
      .catch(() => { if (active) setError("Your mode preference could not be loaded. Advanced Mode remains active."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [user]);

  const value = useMemo<ExperienceModeValue>(() => ({
    mode,
    loading,
    saving,
    error,
    setMode: async (nextMode) => {
      const previous = mode;
      setModeState(nextMode);
      setSaving(true);
      setError(null);
      try {
        setModeState(await saveExperienceMode(nextMode));
      } catch {
        setModeState(previous);
        setError("Your mode preference was not saved. Please try again.");
      } finally {
        setSaving(false);
      }
    },
  }), [loading, mode, saving, error]);

  return <ExperienceModeContext.Provider value={value}>{children}</ExperienceModeContext.Provider>;
}

export function useExperienceMode() {
  const value = useContext(ExperienceModeContext);
  if (!value) throw new Error("useExperienceMode must be used inside ExperienceModeProvider");
  return value;
}
