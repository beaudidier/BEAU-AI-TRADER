import type { InstitutionalAnalysis } from "../types/stock";

type InstitutionalRadarChartProps = {
  engines: InstitutionalAnalysis["engines"];
};

function InstitutionalRadarChart({ engines }: InstitutionalRadarChartProps) {
  const entries = Object.entries(engines);
  const count = entries.length;
  const center = 120;
  const radius = 82;
  const point = (index: number, amount: number) => {
    const angle = (Math.PI * 2 * index) / count - Math.PI / 2;
    return `${(center + Math.cos(angle) * amount).toFixed(1)},${(center + Math.sin(angle) * amount).toFixed(1)}`;
  };
  const axes = entries.map((_, index) => point(index, radius)).join(" ");
  const values = entries.map(([_, result], index) => point(index, (result.score / 100) * radius)).join(" ");

  return <svg viewBox="0 0 240 240" className="mx-auto w-full max-w-65" role="img" aria-label="Institutional engine score radar chart"><polygon points={axes} fill="none" stroke="#334155" strokeWidth="1" />{entries.map((_, index) => <line key={index} x1={center} y1={center} x2={point(index, radius).split(",")[0]} y2={point(index, radius).split(",")[1]} stroke="#1e293b" strokeWidth="1" />)}<polygon points={values} fill="#22d3ee" fillOpacity="0.2" stroke="#22d3ee" strokeWidth="2" />{entries.map(([name, result], index) => { const [x, y] = point(index, radius + 20).split(","); return <text key={name} x={x} y={y} textAnchor="middle" dominantBaseline="middle" fill="#94a3b8" fontSize="8">{name.replace("_", " ")} {result.score}</text>; })}</svg>;
}

export default InstitutionalRadarChart;
