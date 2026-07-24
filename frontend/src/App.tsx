import { useState } from "react";

import ChartPage from "./pages/ChartPage";
import Dashboard from "./pages/Dashboard";
import type { Stock } from "./types/stock";

function App() {
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null);

  if (selectedStock) {
    return <ChartPage stock={selectedStock} onBack={() => setSelectedStock(null)} />;
  }

  return <Dashboard onOpenChart={setSelectedStock} />;
}

export default App;
