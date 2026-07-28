export type SetupPresentation = {
  label: "Waiting for entry" | "Ready for paper trade" | "Blocked" | "Expired";
  tone: "amber" | "emerald" | "rose" | "slate";
  action: string;
};

export function isStalePrice(timestamp: string | null | undefined, now?: number): boolean;
export function setupPresentation(
  status: string,
  plannedEntry: number,
  options?: { stale?: boolean; portfolioBlocked?: boolean },
): SetupPresentation;
