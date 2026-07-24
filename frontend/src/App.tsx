import { useState } from "react";

import ChartPage from "./pages/ChartPage";
import BacktestingPage from "./pages/BacktestingPage";
import Dashboard from "./pages/Dashboard";
import type { AppPage } from "./components/Sidebar";
import type { Stock } from "./types/stock";

function App() {
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null);
  const [page, setPage] = useState<AppPage>("dashboard");

  function navigate(nextPage: AppPage) {
    setSelectedStock(null);
    setPage(nextPage);
  }

  if (selectedStock) {
    return <ChartPage stock={selectedStock} onBack={() => setSelectedStock(null)} onNavigate={navigate} />;
  }

  if (page === "backtesting") {
    return <BacktestingPage onNavigate={navigate} />;
  }

  return <Dashboard onOpenChart={setSelectedStock} onNavigate={navigate} />;
}

export default App;
