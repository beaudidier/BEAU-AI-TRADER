import { userApi } from "./userApi";
import type { UserSettings } from "../types/database";

export type ExperienceMode = "beginner" | "advanced";

export async function loadExperienceMode(): Promise<ExperienceMode> {
  const settings = await userApi.settings() as Partial<UserSettings> | null;
  return settings?.experience_mode === "beginner" ? "beginner" : "advanced";
}

export async function saveExperienceMode(mode: ExperienceMode): Promise<ExperienceMode> {
  const settings = await userApi.updateSettings({ experience_mode: mode }) as Partial<UserSettings>;
  return settings.experience_mode === "beginner" ? "beginner" : "advanced";
}
