import type { Stock, StockChartData, Timeframe } from "../types/stock";

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
