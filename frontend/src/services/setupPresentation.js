const STALE_AFTER_MS = 120 * 60 * 60 * 1000;

export function isStalePrice(timestamp, now = Date.now()) {
  const observedAt = new Date(timestamp ?? "").getTime();
  return !Number.isFinite(observedAt) || now - observedAt > STALE_AFTER_MS;
}

export function setupPresentation(status, plannedEntry, options = {}) {
  if (options.stale) {
    return { label: "Blocked", tone: "rose", action: "Do not act—price data is out of date" };
  }
  if (options.portfolioBlocked) {
    return { label: "Blocked", tone: "rose", action: "Portfolio risk limit reached—do not open another trade" };
  }
  if (status === "expired") {
    return { label: "Expired", tone: "slate", action: "Review another setup" };
  }
  if (status === "invalidated") {
    return { label: "Blocked", tone: "rose", action: "Do not open this trade" };
  }
  if (status === "entry_triggered") {
    return { label: "Ready for paper trade", tone: "emerald", action: "Review and open a paper trade" };
  }
  return { label: "Waiting for entry", tone: "amber", action: `Wait for $${plannedEntry.toFixed(2)}` };
}
