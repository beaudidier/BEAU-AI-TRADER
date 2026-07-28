import { beforeEach, describe, expect, it, vi } from "vitest";

const settings = vi.fn();
const updateSettings = vi.fn();

vi.mock("./userApi", () => ({ userApi: { settings, updateSettings } }));

describe("experience preference persistence", () => {
  beforeEach(() => { settings.mockReset(); updateSettings.mockReset(); });

  it("keeps Advanced Mode as the unchanged default", async () => {
    settings.mockResolvedValue({});
    const { loadExperienceMode } = await import("./experienceMode");
    await expect(loadExperienceMode()).resolves.toBe("advanced");
  });

  it("loads and saves Beginner Mode per user through user settings", async () => {
    settings.mockResolvedValue({ experience_mode: "beginner" });
    updateSettings.mockResolvedValue({ experience_mode: "beginner" });
    const { loadExperienceMode, saveExperienceMode } = await import("./experienceMode");
    await expect(loadExperienceMode()).resolves.toBe("beginner");
    await expect(saveExperienceMode("beginner")).resolves.toBe("beginner");
    expect(updateSettings).toHaveBeenCalledWith({ experience_mode: "beginner" });
  });
});
