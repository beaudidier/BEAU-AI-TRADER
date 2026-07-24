import { useEffect, useState } from "react";

import Header from "../components/Header";
import ScanButton from "../components/ScanButton";
import Sidebar from "../components/Sidebar";
import StockDetailPanel from "../components/StockDetailPanel";
import StockTable from "../components/StockTable";
import { scanMarket } from "../services/api";
import type { Stock } from "../types/stock";

function Dashboard() {
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null);

  async function handleScanMarket() {
    setLoading(true);

    const results = await scanMarket();
    setStocks(results);

    setLoading(false);
  }

  useEffect(() => {
    void handleScanMarket();
  }, []);

  const filteredStocks = stocks.filter((stock) => stock.ticker.toLowerCase().includes(searchTerm.toLowerCase()));

  return (
    <div className="min-h-screen bg-slate-950 font-sans text-slate-100 lg:flex">
      <Sidebar />
      <div className="min-w-0 flex-1">
        <Header />
        <main id="scanner" className="mx-auto max-w-7xl p-5 sm:p-8">
          <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <p className="text-sm font-medium text-cyan-300">Technical analysis</p>
              <h2 className="mt-1 text-2xl font-semibold tracking-tight text-white">Market scanner</h2>
              <p className="mt-2 text-sm text-slate-400">Review ranked trade setups across your watchlist.</p>
            </div>
            <ScanButton loading={loading} onClick={handleScanMarket} />
          </div>
          <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/40 shadow-xl shadow-slate-950/30">
            <div className="flex flex-col gap-4 border-b border-slate-800 p-5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="font-semibold text-white">Scanner results</h3>
                <p className="mt-1 text-sm text-slate-500">{filteredStocks.length} stocks displayed</p>
              </div>
              <label className="relative block">
                <span className="sr-only">Search stocks</span>
                <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-500" aria-hidden="true">⌕</span>
                <input value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Search ticker" className="h-10 w-full rounded-lg border border-slate-700 bg-slate-950 pl-9 pr-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-400 sm:w-56" />
              </label>
            </div>
            <StockTable stocks={filteredStocks} onSelect={setSelectedStock} />
          </section>
        </main>
      </div>
      <StockDetailPanel stock={selectedStock} onClose={() => setSelectedStock(null)} />
    </div>
  );
}

export default Dashboard;
