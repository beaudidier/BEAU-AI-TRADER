import { supabase } from "../lib/supabase";

const apiBaseUrl = "http://127.0.0.1:8000";

async function authenticatedFetch(path: string, options: RequestInit = {}) {
  const { data } = await supabase?.auth.getSession() ?? { data: { session: null } };
  if (!data.session) throw new Error("Your session has expired. Please sign in again.");
  const response = await fetch(`${apiBaseUrl}${path}`, { ...options, headers: { "Content-Type": "application/json", Authorization: `Bearer ${data.session.access_token}`, ...options.headers } });
  if (!response.ok) throw new Error("Unable to complete this request.");
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
  openPaperTrade: (payload: unknown) => authenticatedFetch("/me/paper-trading/open", { method: "POST", body: JSON.stringify(payload) }),
  closePaperTrade: (id: string) => authenticatedFetch(`/me/paper-trading/${id}/close`, { method: "POST" }),
  paperTradeClosePreview: (id: string) => authenticatedFetch(`/me/paper-trading/${id}/close-preview`),
  learningDashboard: (ticker?: string) => authenticatedFetch(`/me/learning/dashboard${ticker ? `?ticker=${encodeURIComponent(ticker)}` : ""}`),
  backtests: () => authenticatedFetch("/me/backtests"),
};
