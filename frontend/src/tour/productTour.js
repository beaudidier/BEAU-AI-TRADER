export const TOUR_VERSION = 2;
export const TOUR_EVENT = "beau:restart-product-tour";

export const productTourSteps = [
  { id: "dashboard", title: "Dashboard overview", target: '[data-tour="dashboard-overview"]', body: "This beginner dashboard answers one question first: what should I do now?" },
  { id: "best-setup", title: "Best current setup", target: '[data-tour="best-setup"]', fallbackTarget: '[data-tour="setup-empty"]', body: "This is the single highest-ranked verified setup. If none exists, waiting is the correct action." },
  { id: "status", title: "Setup status", target: '[data-tour="setup-status"]', body: "The status tells you whether to wait, paper trade, stop, or move on. “Waiting for entry” does not mean buy now." },
  { id: "current-price", title: "Current price", target: '[data-tour="current-price"]', body: "This is where the stock is now. It is not automatically the price where the plan says to enter." },
  { id: "entry", title: "Planned entry", target: '[data-tour="planned-entry"]', body: "Wait for this planned price. A setup can expire or become invalid before an entry happens." },
  { id: "stop", title: "Stop loss", target: '[data-tour="stop-loss"]', body: "This planning level marks where the idea has failed. Stops are not guaranteed fills." },
  { id: "profit-targets", title: "TP1 and TP2 targets", target: '[data-tour="profit-targets"]', body: "TP1 is the first planned profit level; TP2 is higher. Neither target is guaranteed." },
  { id: "maximum-loss", title: "Maximum possible loss", target: '[data-tour="maximum-loss"]', body: "This is planned loss per share before slippage. Gaps can make the actual loss larger." },
  { id: "next-action", title: "Your next action and workspace", target: '[data-tour="next-action"]', body: "Open the workspace to review the chart and risk before any paper trade. Confidence is a rules-based score, not a guaranteed probability of profit." },
  { id: "paper-risk", title: "Paper Trading and portfolio risk", target: '[data-tour="nav-paper-trading"]', body: "Practice here with no real money. Existing portfolio limits can safely block another paper trade." },
  { id: "historical-evidence", title: "Historical Evidence", target: '[data-tour="nav-evidence"]', body: "See how the same fixed rules behaved in older markets. Past results do not guarantee future results." },
  { id: "forward-validation", title: "Forward Validation", target: '[data-tour="nav-forward-validation"]', body: "See results recorded after the rules were fixed. This is useful evidence, not a promise." },
  { id: "feedback", title: "Feedback", target: '[data-tour="nav-feedback"]', body: "Tell us what was unclear or felt risky. Feedback never changes a trade automatically." },
  { id: "mode-switch", title: "Beginner / Advanced switch", target: '[data-tour="mode-switch"]', body: "Beginner Mode keeps decisions plain. Advanced Mode restores scanner scores and technical detail." },
];

export function tourStorageKey(userId) {
  return `beau-product-tour:${userId}`;
}

export function emptyTourProgress() {
  return {
    tour_started_at: null,
    current_step: 0,
    completed_at: null,
    skipped_at: null,
    tour_version: TOUR_VERSION,
  };
}

export function readTourProgress(storage, userId, version = TOUR_VERSION) {
  const empty = { ...emptyTourProgress(), tour_version: version };
  try {
    const saved = JSON.parse(storage.getItem(tourStorageKey(userId)) ?? "null");
    if (!saved || saved.tour_version !== version) return empty;
    return { ...empty, ...saved };
  } catch {
    return empty;
  }
}

export function writeTourProgress(storage, userId, progress) {
  storage.setItem(tourStorageKey(userId), JSON.stringify(progress));
  return progress;
}

export function shouldAutoStart(progress) {
  return !progress.completed_at && !progress.skipped_at;
}

export function startTour(progress, now = new Date().toISOString()) {
  return { ...progress, tour_started_at: progress.tour_started_at ?? now };
}

export function restartTour(version = TOUR_VERSION, now = new Date().toISOString()) {
  return { ...emptyTourProgress(), tour_version: version, tour_started_at: now };
}

export function moveTour(progress, direction, total = productTourSteps.length) {
  const delta = direction === "back" ? -1 : 1;
  return { ...progress, current_step: Math.min(total - 1, Math.max(0, progress.current_step + delta)) };
}

export function finishTour(progress, now = new Date().toISOString()) {
  return { ...progress, current_step: productTourSteps.length - 1, completed_at: now, skipped_at: null };
}

export function skipTour(progress, now = new Date().toISOString()) {
  return { ...progress, skipped_at: now };
}

export function isMobileViewport(width) {
  return width < 640;
}

export function nextAvailableStep(steps, index, isAvailable) {
  for (let candidate = index; candidate < steps.length; candidate += 1) {
    if (isAvailable(steps[candidate])) return candidate;
  }
  return -1;
}

export function keyboardTourAction(key) {
  if (key === "ArrowRight" || key === "Enter") return "next";
  if (key === "ArrowLeft") return "back";
  if (key === "Escape") return "close";
  return null;
}
