import type { Stock } from "../types/stock";

const API_BASE_URL = "http://127.0.0.1:8000";

export async function scanMarket(): Promise<Stock[]> {
  const response = await fetch(`${API_BASE_URL}/scan`);

  return response.json() as Promise<Stock[]>;
}
