import type { Stock } from "../types/stock";

type StockTableProps = {
  stocks: Stock[];
};

function StockTable({ stocks }: StockTableProps) {
  return (
    <table
      style={{
        width: "100%",
        borderCollapse: "collapse",
      }}
    >
      <thead>
        <tr>
          <th align="left">Ticker</th>
          <th align="left">Price</th>
          <th align="left">Score</th>
          <th align="left">Advice</th>
        </tr>
      </thead>

      <tbody>
        {stocks.map((stock) => (
          <tr key={stock.ticker}>
            <td>{stock.ticker}</td>
            <td>${stock.price}</td>
            <td>{stock.score}</td>
            <td>{stock.recommendation}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default StockTable;
