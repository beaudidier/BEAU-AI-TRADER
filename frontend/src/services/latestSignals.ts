import type { LatestSignalEvidenceSummary } from "../types/latestSignals";

export async function getLatestSignalEvidence(signal?: AbortSignal) {
  const response = await fetch("/latest-signals/summary.json", { signal });
  if (!response.ok) {
    throw new Error("Latest signal evidence is temporarily unavailable.");
  }
  const payload = await response.json() as LatestSignalEvidenceSummary;
  if (!payload.all_checks_passed || !Array.isArray(payload.signals)) {
    throw new Error("Latest signal evidence could not be verified.");
  }
  return payload;
}
