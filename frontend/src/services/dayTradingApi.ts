import { API_BASE_URL } from "../config";
import type {
  DayTradingBars,
  DayTradingQuote,
  DayTradingStatus,
  DayTradingTimeframe,
  MarketClock,
  PaperAccount,
  PaperOrderInput,
  PaperPositions,
  RecordingSession,
  RecordingStatus,
  ReplayStatus,
  StreamHealth,
} from "../types/dayTrading";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch {
    throw new Error("The day-trading lab cannot reach the local data service.");
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(payload?.detail || "The day-trading request could not be completed.");
  }
  return response.json() as Promise<T>;
}

export const dayTradingApi = {
  status: () => request<DayTradingStatus>("/day-trading/status"),
  marketClock: () => request<MarketClock>("/day-trading/market-clock"),
  streamHealth: () => request<StreamHealth>("/day-trading/stream-health"),
  quote: (ticker: string) => request<DayTradingQuote>(`/day-trading/quotes/${encodeURIComponent(ticker)}`),
  bars: (ticker: string, timeframe: DayTradingTimeframe) => request<DayTradingBars>(`/day-trading/bars/${encodeURIComponent(ticker)}?timeframe=${timeframe}`),
  paperAccount: () => request<PaperAccount>("/day-trading/paper-account"),
  paperPositions: () => request<PaperPositions>("/day-trading/paper-positions"),
  submitOrder: (input: PaperOrderInput) => request("/day-trading/paper-orders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  }),
  cancelOrder: (orderId: string) => request(`/day-trading/paper-orders/${encodeURIComponent(orderId)}`, { method: "DELETE" }),
  setOrdersEnabled: (enabled: boolean) => request<{ paper_orders_enabled: boolean }>("/day-trading/paper-orders/emergency", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  }),
  recordingStatus: () => request<RecordingStatus>("/day-trading/record/status"),
  recordingSessions: () => request<{ sessions: RecordingSession[] }>("/day-trading/record/sessions"),
  startRecording: () => request<RecordingStatus>("/day-trading/record/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  }),
  stopRecording: () => request<RecordingStatus>("/day-trading/record/stop", { method: "POST" }),
  replayStatus: () => request<ReplayStatus>("/day-trading/replay/status"),
  replayBars: (ticker: string, timeframe: DayTradingTimeframe) => request<DayTradingBars>(`/day-trading/replay/bars/${encodeURIComponent(ticker)}?timeframe=${timeframe}`),
  startReplay: (sessionId: string, speed: ReplayStatus["speed"]) => request<ReplayStatus>("/day-trading/replay/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, speed }),
  }),
  pauseReplay: () => request<ReplayStatus>("/day-trading/replay/pause", { method: "POST" }),
  resumeReplay: () => request<ReplayStatus>("/day-trading/replay/resume", { method: "POST" }),
  seekReplay: (timestamp: string) => request<ReplayStatus>("/day-trading/replay/seek", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ timestamp }),
  }),
  resetReplay: () => request<ReplayStatus>("/day-trading/replay/reset", { method: "POST" }),
};
