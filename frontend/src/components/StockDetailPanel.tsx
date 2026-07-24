import { useEffect, useState } from "react";

import { getInstitutionalAnalysis, getTradePlan } from "../services/api";
import { userApi } from "../services/userApi";
import type { InstitutionalAnalysis, Stock, TradePlan } from "../types/stock";
import AdviceBadge from "./AdviceBadge";
import ExplainableRecommendation from "./ExplainableRecommendation";
import InstitutionalRadarChart from "./InstitutionalRadarChart";
import PaperTradeConfirmationModal from "./PaperTradeConfirmationModal";
import ScoreBadge from "./ScoreBadge";

type StockDetailPanelProps = { stock: Stock | null; onClose: () => void };

const metrics: Array<[keyof Stock, string]> = [["ema20", "EMA 20"], ["ema50", "EMA 50"], ["rsi", "RSI"], ["atr", "ATR"], ["support", "Support"], ["resistance", "Resistance"]];
const planMetrics: Array<[keyof Pick<TradePlan, "entry" | "stop_loss" | "target_1" | "target_2" | "risk_reward_target_1" | "risk_reward_target_2" | "position_size" | "total_position_value">, string, "currency" | "ratio" | "shares"]> = [["entry", "Entry", "currency"], ["stop_loss", "Stop loss", "currency"], ["target_1", "Target 1", "currency"], ["target_2", "Target 2", "currency"], ["risk_reward_target_1", "Target 1 R/R", "ratio"], ["risk_reward_target_2", "Target 2 R/R", "ratio"], ["position_size", "Position size", "shares"], ["total_position_value", "Position value", "currency"]];

function paperTradeBlockReasons(plan: TradePlan, stock: Stock): string[] {
  const reasons: string[] = [];
  const marketValues = [stock.price, plan.current_price, plan.entry, plan.stop_loss, plan.target_1, plan.target_2, plan.risk_per_share, plan.total_position_value, plan.maximum_risk];
  if (plan.recommendation === "SKIP") reasons.push("Paper Buy is unavailable because this setup is marked SKIP.");
  if (plan.position_size <= 0) reasons.push("Paper Buy is unavailable because the suggested quantity is 0 shares.");
  if (plan.risk_reward_target_1 < 1.5) reasons.push("Paper Buy is unavailable because Target 1 risk/reward is below 1.5.");
  if (marketValues.some((value) => !Number.isFinite(value) || value <= 0) || plan.stop_loss >= plan.entry || plan.target_1 <= plan.entry) reasons.push("Paper Buy is unavailable because market data or trade-plan levels are missing or invalid.");
  return reasons;
}

function StockDetailPanel({ stock, onClose }: StockDetailPanelProps) {
  const [tradePlan, setTradePlan] = useState<TradePlan | null>(null);
  const [tradePlanError, setTradePlanError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<InstitutionalAnalysis | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [analysisSaveMessage, setAnalysisSaveMessage] = useState<string | null>(null);
  const [confirmingTrade, setConfirmingTrade] = useState(false);
  const [openingTrade, setOpeningTrade] = useState(false);
  const [paperTradeError, setPaperTradeError] = useState<string | null>(null);
  const [openedTradeId, setOpenedTradeId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setTradePlan(null); setTradePlanError(null); setAnalysis(null); setAnalysisError(null); setConfirmingTrade(false); setPaperTradeError(null); setOpenedTradeId(null);
    if (!stock) return undefined;
    void getTradePlan(stock.ticker).then((plan) => { if (!cancelled) setTradePlan(plan); }).catch((error: unknown) => { if (!cancelled) setTradePlanError(error instanceof Error ? error.message : "Unable to load trade plan."); });
    void getInstitutionalAnalysis(stock.ticker).then((result) => { if (!cancelled) setAnalysis(result); }).catch((error: unknown) => { if (!cancelled) setAnalysisError(error instanceof Error ? error.message : "Unable to load institutional analysis."); });
    return () => { cancelled = true; };
  }, [stock]);

  async function saveAnalysis() { if (!stock || !analysis) return; try { await userApi.saveAnalysis(stock.ticker, analysis); setAnalysisSaveMessage("Analysis saved to your account."); } catch (error) { setAnalysisSaveMessage(error instanceof Error ? error.message : "Unable to save analysis."); } }
  async function confirmPaperTrade() {
    if (!tradePlan) return;
    setOpeningTrade(true); setPaperTradeError(null);
    try {
      const created = await userApi.openPaperTrade({ ticker: tradePlan.ticker, side: "BUY", current_price: tradePlan.current_price, entry_price: tradePlan.entry, stop_loss: tradePlan.stop_loss, target_1: tradePlan.target_1, target_2: tradePlan.target_2, quantity: tradePlan.position_size, confidence_score: tradePlan.confidence_score, recommendation: tradePlan.recommendation, risk_reward_target_1: tradePlan.risk_reward_target_1 }) as { id?: string };
      if (!created.id) throw new Error("Paper trade was created without a position identifier.");
      setOpenedTradeId(created.id); setConfirmingTrade(false);
    } catch (error) { setPaperTradeError(error instanceof Error ? error.message : "Unable to open paper trade."); } finally { setOpeningTrade(false); }
  }

  if (!stock) return null;
  const blockReasons = tradePlan ? paperTradeBlockReasons(tradePlan, stock) : [];
  return <div className="fixed inset-0 z-30 flex justify-end bg-slate-950/60 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label={`${stock.ticker} details`}><button className="flex-1 cursor-default" onClick={onClose} aria-label="Close detail panel" /><section className="h-full w-full max-w-md overflow-y-auto border-l border-slate-800 bg-slate-950 p-6 shadow-2xl sm:p-8"><div className="flex items-start justify-between gap-4"><div><p className="text-sm text-slate-500">Stock details</p><h2 className="mt-1 text-3xl font-semibold tracking-tight text-white">{stock.ticker}</h2><p className="mt-2 text-xl font-medium text-slate-200">${stock.price.toFixed(2)}</p></div><button onClick={onClose} className="grid size-9 place-items-center rounded-lg border border-slate-700 text-slate-400 transition hover:border-slate-600 hover:text-white" aria-label="Close details">×</button></div><div className="mt-7 flex items-center gap-3"><ScoreBadge score={stock.score} /><AdviceBadge advice={stock.recommendation} /></div><dl className="mt-8 grid grid-cols-2 gap-3">{metrics.map(([key, label]) => <div key={key} className="rounded-lg border border-slate-800 bg-slate-900/60 p-4"><dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt><dd className="mt-1 font-mono text-sm font-semibold text-slate-200">${(stock[key] as number).toFixed(2)}</dd></div>)}</dl><div className="mt-8"><h3 className="text-sm font-semibold text-white">Setup signals</h3><ul className="mt-3 space-y-2">{stock.reasons.map((reason) => <li key={reason} className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-slate-300">{reason}</li>)}</ul></div><div className="mt-8 border-t border-slate-800 pt-8"><div className="flex items-center justify-between gap-4"><div><p className="text-sm font-semibold text-white">Institutional analysis</p><p className="mt-1 text-xs text-slate-500">Seven-factor weighted model</p></div>{analysis && <ScoreBadge score={analysis.overall_score} />}</div>{!analysis && !analysisError && <div className="mt-5 flex items-center gap-3 text-sm text-slate-400"><span className="size-4 animate-spin rounded-full border-2 border-cyan-300 border-t-transparent" /> Loading analysis…</div>}{analysisError && <p className="mt-5 rounded-lg border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-200">{analysisError}</p>}{analysis && <><div className="mt-4 flex items-center gap-3"><AdviceBadge advice={analysis.recommendation} /><span className="text-sm text-slate-400">Overall {analysis.overall_score}/100</span><button onClick={saveAnalysis} className="ml-auto text-xs font-semibold text-cyan-300 hover:text-cyan-200">Save analysis</button></div>{analysisSaveMessage && <p className="mt-3 text-xs text-slate-400">{analysisSaveMessage}</p>}<InstitutionalRadarChart engines={analysis.engines} /><ul className="mt-4 space-y-2">{Object.entries(analysis.engines).map(([name, result]) => <li key={name} className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-slate-300"><span className="font-medium text-white">{name.replace("_", " ")}: {result.score}</span><span className="block pt-1 text-xs text-slate-500">{result.explanation}</span></li>)}</ul><ExplainableRecommendation explanation={analysis.explanation} /></>}</div><div className="mt-8 border-t border-slate-800 pt-8"><div className="flex items-center justify-between gap-4"><div><p className="text-sm font-semibold text-white">Trade plan</p><p className="mt-1 text-xs text-slate-500">Based on a $10,000 account with 1% risk.</p></div>{tradePlan && <ScoreBadge score={tradePlan.confidence_score} />}</div>{!tradePlan && !tradePlanError && <div className="mt-5 flex items-center gap-3 text-sm text-slate-400"><span className="size-4 animate-spin rounded-full border-2 border-cyan-300 border-t-transparent" /> Loading trade plan…</div>}{tradePlanError && <div className="mt-5 rounded-lg border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-200">{tradePlanError}</div>}{tradePlan && <><div className="mt-5 flex items-center gap-3"><AdviceBadge advice={tradePlan.recommendation} /><span className="text-sm text-slate-400">Confidence {tradePlan.confidence_score}/100</span></div><dl className="mt-5 grid grid-cols-2 gap-3">{planMetrics.map(([key, label, format]) => { const value = tradePlan[key]; const displayValue = format === "currency" ? `$${value.toFixed(2)}` : format === "ratio" ? `${value.toFixed(2)}R` : `${value} shares`; return <div key={key} className="rounded-lg border border-slate-800 bg-slate-900/60 p-3"><dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt><dd className="mt-1 font-mono text-sm font-semibold text-slate-200">{displayValue}</dd></div>; })}</dl><ExplainableRecommendation explanation={tradePlan.explanation} /><p className="mt-5 rounded-lg border border-amber-400/20 bg-amber-400/10 p-3 text-xs leading-5 text-amber-100">Stops and targets are reference levels only and are not automatically executed.</p><div className="mt-6 border-t border-slate-800 pt-6">{blockReasons.length > 0 ? <div className="rounded-lg border border-rose-400/20 bg-rose-400/10 p-3"><p className="text-sm font-semibold text-rose-200">Paper Buy blocked</p><ul className="mt-2 space-y-1 text-xs leading-5 text-rose-100">{blockReasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></div> : <button type="button" onClick={() => { setPaperTradeError(null); setConfirmingTrade(true); }} disabled={openingTrade} className="w-full rounded-lg bg-emerald-400 px-3 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:opacity-60">Paper Buy</button>}{paperTradeError && !confirmingTrade && <p className="mt-3 rounded-lg border border-rose-400/20 bg-rose-400/10 p-3 text-xs text-rose-200">{paperTradeError}</p>}{openedTradeId && <div className="mt-4 rounded-lg border border-emerald-400/20 bg-emerald-400/10 p-4"><p className="text-sm font-semibold text-emerald-200">Paper position opened successfully.</p><button type="button" onClick={() => { window.location.assign(`/paper-trading?position=${openedTradeId}`); }} className="mt-3 rounded-lg border border-emerald-400/40 px-3 py-2 text-sm font-semibold text-emerald-200">View Position</button></div>}</div></>}</div></section>{confirmingTrade && tradePlan && <PaperTradeConfirmationModal plan={tradePlan} loading={openingTrade} error={paperTradeError} onCancel={() => { if (!openingTrade) { setConfirmingTrade(false); setPaperTradeError(null); } }} onConfirm={() => void confirmPaperTrade()} />}</div>;
}

export default StockDetailPanel;
