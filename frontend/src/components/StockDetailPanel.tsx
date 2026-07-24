import { useEffect, useState } from "react";

import { getInstitutionalAnalysis, getTradePlan } from "../services/api";
import { userApi } from "../services/userApi";
import type { InstitutionalAnalysis, Stock, TradePlan } from "../types/stock";
import AdviceBadge from "./AdviceBadge";
import InstitutionalRadarChart from "./InstitutionalRadarChart";
import ScoreBadge from "./ScoreBadge";

type StockDetailPanelProps = {
  stock: Stock | null;
  onClose: () => void;
};

const metrics: Array<[keyof Stock, string]> = [
  ["ema20", "EMA 20"],
  ["ema50", "EMA 50"],
  ["rsi", "RSI"],
  ["atr", "ATR"],
  ["support", "Support"],
  ["resistance", "Resistance"],
];

const planMetrics: Array<[keyof Pick<TradePlan, "entry" | "stop_loss" | "target_1" | "target_2" | "risk_reward_target_1" | "risk_reward_target_2" | "position_size" | "total_position_value">, string, "currency" | "ratio" | "shares"]> = [
  ["entry", "Entry", "currency"],
  ["stop_loss", "Stop loss", "currency"],
  ["target_1", "Target 1", "currency"],
  ["target_2", "Target 2", "currency"],
  ["risk_reward_target_1", "Target 1 R/R", "ratio"],
  ["risk_reward_target_2", "Target 2 R/R", "ratio"],
  ["position_size", "Position size", "shares"],
  ["total_position_value", "Position value", "currency"],
];

function StockDetailPanel({ stock, onClose }: StockDetailPanelProps) {
  const [tradePlan, setTradePlan] = useState<TradePlan | null>(null);
  const [tradePlanError, setTradePlanError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<InstitutionalAnalysis | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [analysisSaveMessage, setAnalysisSaveMessage] = useState<string | null>(null);
  const [paperTradeMessage, setPaperTradeMessage] = useState<string | null>(null);
  const [paperTradeLoading, setPaperTradeLoading] = useState<"BUY" | "SELL" | null>(null);

  async function saveAnalysis() {
    if (!stock || !analysis) return;
    try { await userApi.saveAnalysis(stock.ticker, analysis); setAnalysisSaveMessage("Analysis saved to your account."); }
    catch (error) { setAnalysisSaveMessage(error instanceof Error ? error.message : "Unable to save analysis."); }
  }

  async function openPaperTrade(side: "BUY" | "SELL") {
    if (!stock || !tradePlan) return;
    setPaperTradeLoading(side);
    setPaperTradeMessage(null);
    try {
      await userApi.openPaperTrade({ ticker: stock.ticker, side, entry_price: tradePlan.entry, stop_loss: tradePlan.stop_loss, target_1: tradePlan.target_1, target_2: tradePlan.target_2, quantity: tradePlan.position_size, confidence_score: tradePlan.confidence_score, recommendation: tradePlan.recommendation });
      setPaperTradeMessage(`Paper ${side.toLowerCase()} position opened using this trade plan.`);
    } catch (error) {
      setPaperTradeMessage(error instanceof Error ? error.message : "Unable to open paper trade.");
    } finally {
      setPaperTradeLoading(null);
    }
  }

  useEffect(() => {
    let cancelled = false;

    if (!stock) {
      setTradePlan(null);
      setTradePlanError(null);
      setAnalysis(null);
      setAnalysisError(null);
      return undefined;
    }

    const ticker = stock.ticker;
    setTradePlan(null);
    setTradePlanError(null);
    setAnalysis(null);
    setAnalysisError(null);

    async function loadTradePlan() {
      try {
        const plan = await getTradePlan(ticker);
        if (!cancelled) setTradePlan(plan);
      } catch (error) {
        if (!cancelled) setTradePlanError(error instanceof Error ? error.message : "Unable to load trade plan.");
      }
    }

    void loadTradePlan();

    async function loadAnalysis() {
      try {
        const result = await getInstitutionalAnalysis(ticker);
        if (!cancelled) setAnalysis(result);
      } catch (error) {
        if (!cancelled) setAnalysisError(error instanceof Error ? error.message : "Unable to load institutional analysis.");
      }
    }

    void loadAnalysis();

    return () => { cancelled = true; };
  }, [stock]);

  if (!stock) return null;

  return (
    <div className="fixed inset-0 z-30 flex justify-end bg-slate-950/60 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label={`${stock.ticker} details`}>
      <button className="flex-1 cursor-default" onClick={onClose} aria-label="Close detail panel" />
      <section className="h-full w-full max-w-md overflow-y-auto border-l border-slate-800 bg-slate-950 p-6 shadow-2xl sm:p-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm text-slate-500">Stock details</p>
            <h2 className="mt-1 text-3xl font-semibold tracking-tight text-white">{stock.ticker}</h2>
            <p className="mt-2 text-xl font-medium text-slate-200">${stock.price.toFixed(2)}</p>
          </div>
          <button onClick={onClose} className="grid size-9 place-items-center rounded-lg border border-slate-700 text-slate-400 transition hover:border-slate-600 hover:text-white" aria-label="Close details">×</button>
        </div>
        <div className="mt-7 flex items-center gap-3"><ScoreBadge score={stock.score} /><AdviceBadge advice={stock.recommendation} /></div>
        <dl className="mt-8 grid grid-cols-2 gap-3">
          {metrics.map(([key, label]) => (
            <div key={key} className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
              <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
              <dd className="mt-1 font-mono text-sm font-semibold text-slate-200">{typeof stock[key] === "number" ? `$${(stock[key] as number).toFixed(2)}` : stock[key]}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-8">
          <h3 className="text-sm font-semibold text-white">Setup signals</h3>
          <ul className="mt-3 space-y-2">
            {stock.reasons.map((reason) => <li key={reason} className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-slate-300">{reason}</li>)}
          </ul>
        </div>
        <div className="mt-8 border-t border-slate-800 pt-8">
          <div className="flex items-center justify-between gap-4"><div><p className="text-sm font-semibold text-white">Institutional analysis</p><p className="mt-1 text-xs text-slate-500">Seven-factor weighted model</p></div>{analysis && <ScoreBadge score={analysis.overall_score} />}</div>
          {!analysis && !analysisError && <div className="mt-5 flex items-center gap-3 text-sm text-slate-400"><span className="size-4 animate-spin rounded-full border-2 border-cyan-300 border-t-transparent" aria-hidden="true" /> Loading analysis…</div>}
          {analysisError && <p className="mt-5 rounded-lg border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-200">{analysisError}</p>}
          {analysis && <><div className="mt-4 flex items-center gap-3"><AdviceBadge advice={analysis.recommendation} /><span className="text-sm text-slate-400">Overall {analysis.overall_score}/100</span><button onClick={saveAnalysis} className="ml-auto text-xs font-semibold text-cyan-300 hover:text-cyan-200">Save analysis</button></div>{analysisSaveMessage && <p className="mt-3 text-xs text-slate-400">{analysisSaveMessage}</p>}<InstitutionalRadarChart engines={analysis.engines} /><ul className="mt-4 space-y-2">{Object.entries(analysis.engines).map(([name, result]) => <li key={name} className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-slate-300"><span className="font-medium text-white">{name.replace("_", " ")}: {result.score}</span><span className="block pt-1 text-xs text-slate-500">{result.explanation}</span></li>)}</ul>{analysis.strengths.length > 0 && <p className="mt-4 text-xs text-emerald-300">Strengths: {analysis.strengths.join(", ")}</p>}{analysis.weaknesses.length > 0 && <p className="mt-2 text-xs text-rose-300">Weaknesses: {analysis.weaknesses.join(", ")}</p>}{analysis.warnings.length > 0 && <ul className="mt-3 space-y-1">{analysis.warnings.map((warning) => <li key={warning} className="text-xs text-amber-200">{warning}</li>)}</ul>}</>}
        </div>
        <div className="mt-8 border-t border-slate-800 pt-8">
          <div className="flex items-center justify-between gap-4">
            <div><p className="text-sm font-semibold text-white">Trade plan</p><p className="mt-1 text-xs text-slate-500">Based on a $10,000 account with 1% risk.</p></div>
            {tradePlan && <ScoreBadge score={tradePlan.confidence_score} />}
          </div>
          {!tradePlan && !tradePlanError && <div className="mt-5 flex items-center gap-3 text-sm text-slate-400"><span className="size-4 animate-spin rounded-full border-2 border-cyan-300 border-t-transparent" aria-hidden="true" /> Loading trade plan…</div>}
          {tradePlanError && <div className="mt-5 rounded-lg border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-200">{tradePlanError}</div>}
          {tradePlan && <>
            <div className="mt-5 flex items-center gap-3"><AdviceBadge advice={tradePlan.recommendation} /><span className="text-sm text-slate-400">Confidence {tradePlan.confidence_score}/100</span></div>
            <dl className="mt-5 grid grid-cols-2 gap-3">
              {planMetrics.map(([key, label, format]) => {
                const value = tradePlan[key];
                const displayValue = format === "currency" ? `$${value.toFixed(2)}` : format === "ratio" ? `${value.toFixed(2)}R` : `${value} shares`;

                return <div key={key} className="rounded-lg border border-slate-800 bg-slate-900/60 p-3"><dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt><dd className="mt-1 font-mono text-sm font-semibold text-slate-200">{displayValue}</dd></div>;
              })}
            </dl>
            <div className="mt-6"><h3 className="text-sm font-semibold text-white">Plan reasons</h3><ul className="mt-3 space-y-2">{tradePlan.reasons.map((reason) => <li key={reason} className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-slate-300">{reason}</li>)}</ul></div>
            {tradePlan.warnings.length > 0 && <div className="mt-6"><h3 className="text-sm font-semibold text-amber-200">Warnings</h3><ul className="mt-3 space-y-2">{tradePlan.warnings.map((warning) => <li key={warning} className="rounded-lg border border-amber-400/20 bg-amber-400/10 px-3 py-2 text-sm text-amber-100">{warning}</li>)}</ul></div>}
            <div className="mt-6 border-t border-slate-800 pt-6"><p className="text-xs leading-5 text-slate-500">Paper trading uses simulated funds only. The entry, stop, targets, position size, and confidence are saved with the trade.</p><div className="mt-4 grid grid-cols-2 gap-3"><button type="button" onClick={() => void openPaperTrade("BUY")} disabled={paperTradeLoading !== null} className="rounded-lg bg-emerald-400 px-3 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:opacity-60">{paperTradeLoading === "BUY" ? "Opening…" : "Paper Buy"}</button><button type="button" onClick={() => void openPaperTrade("SELL")} disabled={paperTradeLoading !== null} className="rounded-lg border border-rose-400/40 px-3 py-2.5 text-sm font-semibold text-rose-200 transition hover:bg-rose-400/10 disabled:opacity-60">{paperTradeLoading === "SELL" ? "Opening…" : "Paper Sell"}</button></div>{paperTradeMessage && <p className="mt-3 text-xs text-slate-400">{paperTradeMessage}</p>}</div>
          </>}
        </div>
      </section>
    </div>
  );
}

export default StockDetailPanel;
