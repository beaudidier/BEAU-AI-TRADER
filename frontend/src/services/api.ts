import type { BacktestRequest, BacktestResult, BacktestTrade, CoachAnalysis, DailyBriefing, InstitutionalAnalysis, Stock, StockChartData, Timeframe, TradePlan } from "../types/stock";

const API_BASE_URL = "http://127.0.0.1:8000";

export async function scanMarket(): Promise<Stock[]> {
  const response = await fetch(`${API_BASE_URL}/scan`);

  return response.json() as Promise<Stock[]>;
}

export async function getStockChart(ticker: string, timeframe: Timeframe): Promise<StockChartData> {
  const response = await fetch(`${API_BASE_URL}/stocks/${ticker}/history?timeframe=${timeframe}`);

  if (!response.ok) {
    throw new Error("Unable to load chart data. Please try again.");
  }

  return response.json() as Promise<StockChartData>;
}

export async function getTradePlan(ticker: string, accountSize = 10000, riskPercent = 1): Promise<TradePlan> {
  const parameters = new URLSearchParams({ account_size: String(accountSize), risk_percent: String(riskPercent) });
  const response = await fetch(`${API_BASE_URL}/trade-plan/${ticker}?${parameters}`);

  if (!response.ok) {
    throw new Error("Unable to load trade plan. Please try again.");
  }

  return response.json() as Promise<TradePlan>;
}

export async function runBacktest(request: BacktestRequest): Promise<BacktestResult> {
  const response = await fetch(`${API_BASE_URL}/backtest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error("Unable to run backtest. Check the selected inputs and try again.");
  }

  return response.json() as Promise<BacktestResult>;
}

export async function analyzeTradeCoach(trade: BacktestTrade): Promise<CoachAnalysis> {
  const response = await fetch(`${API_BASE_URL}/coach/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(trade),
  });

  if (!response.ok) {
    throw new Error("Unable to analyze this completed trade. Please try again.");
  }

  return response.json() as Promise<CoachAnalysis>;
}

export async function getInstitutionalAnalysis(ticker: string): Promise<InstitutionalAnalysis> {
  const response = await fetch(`${API_BASE_URL}/analysis/${ticker}`);
  if (!response.ok) throw new Error("Unable to load institutional analysis.");

  return response.json() as Promise<InstitutionalAnalysis>;
}

export async function getDailyBriefing(): Promise<DailyBriefing> {
  const response = await fetch(`${API_BASE_URL}/briefing`);
  if (!response.ok) throw new Error("Unable to load the daily briefing.");
  return response.json() as Promise<DailyBriefing>;
}
