import { useEffect, useState } from "react";

import Header from "../components/Header";
import ScanButton from "../components/ScanButton";
import StockTable from "../components/StockTable";
import { scanMarket } from "../services/api";
import type { Stock } from "../types/stock";

function Dashboard() {
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [loading, setLoading] = useState(false);

  async function handleScanMarket() {
    setLoading(true);

    const results = await scanMarket();
    setStocks(results);

    setLoading(false);
  }

  useEffect(() => {
    void handleScanMarket();
  }, []);

  return (
    <div
      style={{
        background: "#111827",
        color: "white",
        minHeight: "100vh",
        padding: "40px",
        fontFamily: "Arial",
      }}
    >
      <Header title="🚀 BEAU AI TRADER" />
      <ScanButton loading={loading} onClick={handleScanMarket} />
      <StockTable stocks={stocks} />
    </div>
  );
}

export default Dashboard;
