import type { EvidenceSummary } from "../types/evidence";

export async function getHistoricalEvidence(signal?: AbortSignal): Promise<EvidenceSummary> {
  const response = await fetch("/evidence/summary.json", { signal });
  if (!response.ok) {
    throw new Error("Historical evidence is temporarily unavailable.");
  }
  const result = await response.json() as EvidenceSummary;
  if (!Array.isArray(result.examples) || result.example_count !== result.examples.length) {
    throw new Error("Historical evidence could not be verified.");
  }
  return result;
}
