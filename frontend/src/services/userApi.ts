import { supabase } from "../lib/supabase";
import { API_BASE_URL } from "../config";

const technicalMessage = /(traceback|exception|stack trace|keyerror|typeerror|supabase|postgrest|fetch failed|internal server error)/i;

function safeApiMessage(
  status: number,
  detail: string | { message?: string; capacity_resets_at?: string } | undefined,
) {
  if (status === 401) {
    return "Your session has expired. Please sign in again.";
  }
  if (status === 429) {
    return "Too many requests were made. Please wait a moment and try again.";
  }
  if (status >= 500) {
    return "The service is temporarily unavailable. Your saved data has not been changed.";
  }

  let message = typeof detail === "string"
    ? detail
    : detail?.message ?? "Unable to complete this request.";
  if (technicalMessage.test(message)) {
    message = "Unable to complete this request right now. Please try again.";
  }
  if (detail && typeof detail === "object" && detail.capacity_resets_at) {
    const reset = new Date(detail.capacity_resets_at);
    if (!Number.isNaN(reset.getTime())) {
      message += ` Capacity resets ${reset.toLocaleString()}.`;
    }
  }
  return message;
}

function handleExpiredSession() {
  void supabase?.auth.signOut({ scope: "local" });
  if (
    typeof window !== "undefined"
    && !window.location.pathname.startsWith("/login")
  ) {
    window.location.assign("/login?reason=session-expired");
  }
}

async function authenticatedFetch(path: string, options: RequestInit = {}) {
  const { data } = await supabase?.auth.getSession() ?? { data: { session: null } };
  if (!data.session) {
    handleExpiredSession();
    throw new Error("Your session has expired. Please sign in again.");
  }
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers: { "Content-Type": "application/json", Authorization: `Bearer ${data.session.access_token}`, ...options.headers } });
  if (!response.ok) {
    let detail: string | { message?: string; capacity_resets_at?: string } | undefined;
    try {
      const payload = await response.json() as {
        detail?: string | {
          message?: string;
          capacity_resets_at?: string;
        };
      };
      detail = payload.detail;
    } catch {
      // Keep the non-technical fallback when the server has no JSON response.
    }
    if (response.status === 401) handleExpiredSession();
    throw new Error(safeApiMessage(response.status, detail));
  }
  return response.status === 204 ? null : response.json();
}

export const userApi = {
  me: () => authenticatedFetch("/me"),
  profile: (payload: unknown) => authenticatedFetch("/me/profile", { method: "PATCH", body: JSON.stringify(payload) }),
  settings: () => authenticatedFetch("/me/settings"),
  updateSettings: (payload: unknown) => authenticatedFetch("/me/settings", { method: "PATCH", body: JSON.stringify(payload) }),
  watchlists: () => authenticatedFetch("/me/watchlists"),
  createWatchlist: (name: string) => authenticatedFetch("/me/watchlists", { method: "POST", body: JSON.stringify({ name }) }),
  addWatchlistItem: (id: string, ticker: string) => authenticatedFetch(`/me/watchlists/${id}/items`, { method: "POST", body: JSON.stringify({ ticker }) }),
  deleteWatchlist: (id: string) => authenticatedFetch(`/me/watchlists/${id}`, { method: "DELETE" }),
  saveAnalysis: (ticker: string, analysisJson: unknown) => authenticatedFetch("/me/saved-analyses", { method: "POST", body: JSON.stringify({ ticker, analysis_json: analysisJson }) }),
  saveBacktest: (ticker: string, parameters: unknown, results: unknown) => authenticatedFetch("/me/backtests/save", { method: "POST", body: JSON.stringify({ ticker, parameters, results }) }),
  paperPortfolio: () => authenticatedFetch("/me/paper-trading/portfolio"),
  paperTrade: (id: string) => authenticatedFetch(`/me/paper-trading/${id}`),
  updatePaperTradeJournal: (id: string, payload: unknown) => authenticatedFetch(`/me/paper-trading/${id}/journal`, { method: "PATCH", body: JSON.stringify(payload) }),
  openPaperTrade: (payload: unknown) => authenticatedFetch("/me/paper-trading/open", { method: "POST", body: JSON.stringify(payload) }),
  closePaperTrade: (id: string) => authenticatedFetch(`/me/paper-trading/${id}/close`, { method: "POST" }),
  paperTradeClosePreview: (id: string) => authenticatedFetch(`/me/paper-trading/${id}/close-preview`),
  learningDashboard: (ticker?: string) => authenticatedFetch(`/me/learning/dashboard${ticker ? `?ticker=${encodeURIComponent(ticker)}` : ""}`),
  backtests: () => authenticatedFetch("/me/backtests"),
  forwardValidationDashboard: () => authenticatedFetch("/me/forward-validation/dashboard"),
  runForwardValidation: () => authenticatedFetch("/me/forward-validation/run", { method: "POST" }),
  scanForwardValidation: () => authenticatedFetch("/me/forward-validation/scan", { method: "POST" }),
  refreshForwardValidation: () => authenticatedFetch("/me/forward-validation/refresh", { method: "POST" }),
  privateBeta: () => authenticatedFetch("/me/private-beta"),
  betaReadiness: () => authenticatedFetch("/me/private-beta/readiness"),
  feedback: () => authenticatedFetch("/me/feedback"),
  submitFeedback: (payload: unknown) => authenticatedFetch("/me/feedback", { method: "POST", body: JSON.stringify(payload) }),
  signalReviews: () => authenticatedFetch("/me/signal-reviews"),
  submitSignalReview: (payload: unknown) => authenticatedFetch("/me/signal-reviews", { method: "POST", body: JSON.stringify(payload) }),
  recordFrontendError: (payload: unknown) => authenticatedFetch("/me/monitoring/frontend", { method: "POST", body: JSON.stringify(payload) }),
  betaInvites: () => authenticatedFetch("/me/beta-invites"),
  createBetaInvite: (payload: unknown) => authenticatedFetch("/me/beta-invites", { method: "POST", body: JSON.stringify(payload) }),
  revokeBetaInvite: (id: string) => authenticatedFetch(`/me/beta-invites/${id}/revoke`, { method: "POST" }),
};
