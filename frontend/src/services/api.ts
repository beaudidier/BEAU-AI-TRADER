import type { BacktestRequest, BacktestResult, BacktestTrade, CoachAnalysis, DailyBriefing, InstitutionalAnalysis, MarketDataTransparency, ScanJob, Stock, StockChartData, Timeframe, TradePlan, TradingStrategy, ValidationDashboard } from "../types/stock";
import { API_BASE_URL } from "../config";

export async function getStrategies(): Promise<TradingStrategy[]> {
  const response = await fetch(`${API_BASE_URL}/strategies`);
  if (!response.ok) throw new Error("Unable to load trading strategies.");
  return response.json() as Promise<TradingStrategy[]>;
}

export async function scanMarket(strategy = "swing_trading"): Promise<Stock[]> {
  const parameters = new URLSearchParams({ strategy });
  const response = await fetch(`${API_BASE_URL}/scan?${parameters}`);

  if (!response.ok) {
    throw new Error("The market scanner is temporarily unavailable.");
  }

  return response.json() as Promise<Stock[]>;
}

export async function createScanJob(market: "stocks" | "crypto", universe: string): Promise<ScanJob> {
  const response = await fetch(`${API_BASE_URL}/scan/jobs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ market, universe }) });
  if (!response.ok) throw new Error("Unable to start this market scan.");
  return response.json() as Promise<ScanJob>;
}

export async function getScanJob(jobId: string): Promise<ScanJob> {
  const response = await fetch(`${API_BASE_URL}/scan/jobs/${jobId}`);
  if (!response.ok) throw new Error("Unable to check scan progress.");
  return response.json() as Promise<ScanJob>;
}

export async function getScanJobResults(jobId: string): Promise<{ job: ScanJob; results: Stock[]; failed_symbols: string[] }> {
  const response = await fetch(`${API_BASE_URL}/scan/jobs/${jobId}/results`);
  if (!response.ok) throw new Error("Unable to load scan results.");
  return response.json() as Promise<{ job: ScanJob; results: Stock[]; failed_symbols: string[] }>;
}

export async function getValidationDashboard(): Promise<ValidationDashboard> {
  const response = await fetch(`${API_BASE_URL}/validation/dashboard`);
  if (!response.ok) throw new Error("Unable to load validation metrics.");
  return response.json() as Promise<ValidationDashboard>;
}

export async function getStockChart(ticker: string, timeframe: Timeframe): Promise<StockChartData> {
  const response = await fetch(`${API_BASE_URL}/stocks/${ticker}/history?timeframe=${timeframe}`);

  if (!response.ok) {
    throw new Error("Unable to load chart data. Please try again.");
  }

  return response.json() as Promise<StockChartData>;
}

export async function getMarketDataTransparency(ticker: string): Promise<MarketDataTransparency> {
  const response = await fetch(`${API_BASE_URL}/market-data/${ticker}/transparency`);
  if (!response.ok) {
    throw new Error("Market-data timing details are temporarily unavailable.");
  }
  return response.json() as Promise<MarketDataTransparency>;
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
