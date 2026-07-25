import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import Header from "../components/Header";
import Sidebar, { type AppPage } from "../components/Sidebar";
import { getLatestSignalEvidence } from "../services/latestSignals";
import { userApi } from "../services/userApi";
import type { BetaFeedback, FeedbackCategory, FeedbackSeverity, ProfessionalSignalReview } from "../types/database";
import type { LatestSignalEvidence } from "../types/latestSignals";

type FeedbackPageProps = {
  onNavigate: (page: AppPage) => void;
};

const categories: FeedbackCategory[] = ["strategy logic", "entry/stop/target", "chart", "risk", "data quality", "usability", "bug", "missing context"];
const severities: FeedbackSeverity[] = ["low", "medium", "high", "critical"];
const pageOptions = ["Dashboard", "Latest Signals", "Trade Workspace", "Paper Trading", "Evidence", "Forward Validation", "Learning", "Other"];

type ReviewAnswers = {
  would_take_setup: boolean | null;
  entry_logical: boolean | null;
  stop_structurally_correct: boolean | null;
  targets_realistic: boolean | null;
  relevant_context_missing: boolean | null;
  market_regime_makes_sense: boolean | null;
};

const defaultReview: ReviewAnswers = {
  would_take_setup: null,
  entry_logical: null,
  stop_structurally_correct: null,
  targets_realistic: null,
  relevant_context_missing: null,
  market_regime_makes_sense: null,
};

function BinaryQuestion({ label, value, onChange }: { label: string; value: boolean | null; onChange: (value: boolean) => void }) {
  return (
    <fieldset className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
      <legend className="px-1 text-sm font-medium text-slate-200">{label}</legend>
      <div className="mt-2 flex gap-2">
        {[true, false].map((option) => (
          <button key={String(option)} type="button" onClick={() => onChange(option)} className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${value === option ? "bg-cyan-400 text-slate-950" : "border border-slate-700 text-slate-300 hover:border-slate-600"}`}>
            {option ? "Yes" : "No"}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

export default function FeedbackPage({ onNavigate }: FeedbackPageProps) {
  const [searchParams] = useSearchParams();
  const queryTicker = searchParams.get("ticker")?.toUpperCase() ?? "";
  const [feedbackPage, setFeedbackPage] = useState("Trade Workspace");
  const [ticker, setTicker] = useState(queryTicker);
  const [category, setCategory] = useState<FeedbackCategory>("strategy logic");
  const [severity, setSeverity] = useState<FeedbackSeverity>("medium");
  const [message, setMessage] = useState("");
  const [screenshotReference, setScreenshotReference] = useState("");
  const [signals, setSignals] = useState<LatestSignalEvidence[]>([]);
  const [selectedSignalId, setSelectedSignalId] = useState("");
  const [review, setReview] = useState<ReviewAnswers>(defaultReview);
  const [reviewConfidence, setReviewConfidence] = useState(5);
  const [reviewNotes, setReviewNotes] = useState("");
  const [feedbackRows, setFeedbackRows] = useState<BetaFeedback[]>([]);
  const [reviewRows, setReviewRows] = useState<ProfessionalSignalReview[]>([]);
  const [feedbackStatus, setFeedbackStatus] = useState<string | null>(null);
  const [reviewStatus, setReviewStatus] = useState<string | null>(null);
  const [loadingFeedback, setLoadingFeedback] = useState(false);
  const [loadingReview, setLoadingReview] = useState(false);

  useEffect(() => {
    void Promise.allSettled([
      userApi.feedback(),
      userApi.signalReviews(),
      getLatestSignalEvidence(),
    ]).then(([feedbackResult, reviewResult, signalResult]) => {
      if (feedbackResult.status === "fulfilled") setFeedbackRows(feedbackResult.value as BetaFeedback[]);
      if (reviewResult.status === "fulfilled") setReviewRows(reviewResult.value as ProfessionalSignalReview[]);
      if (signalResult.status === "fulfilled") {
        setSignals(signalResult.value.signals);
        const preferred = signalResult.value.signals.find((item) => item.ticker === queryTicker) ?? signalResult.value.signals[0];
        if (preferred) {
          setSelectedSignalId(preferred.id);
          setTicker((current) => current || preferred.ticker);
        }
      }
    });
  }, [queryTicker]);

  const selectedSignal = useMemo(() => signals.find((item) => item.id === selectedSignalId), [selectedSignalId, signals]);

  async function submitFeedback(event: React.FormEvent) {
    event.preventDefault();
    setLoadingFeedback(true);
    setFeedbackStatus(null);
    try {
      const created = await userApi.submitFeedback({
        page: feedbackPage,
        ticker: ticker || null,
        category,
        severity,
        message,
        screenshot_reference: screenshotReference || null,
      }) as BetaFeedback;
      setFeedbackRows((rows) => [created, ...rows]);
      setMessage("");
      setScreenshotReference("");
      setFeedbackStatus("Feedback recorded. Thank you for the precise review.");
    } catch (error) {
      setFeedbackStatus(error instanceof Error ? error.message : "Feedback could not be recorded.");
    } finally {
      setLoadingFeedback(false);
    }
  }

  async function submitReview(event: React.FormEvent) {
    event.preventDefault();
    const reviewTicker = selectedSignal?.ticker ?? ticker;
    if (!reviewTicker) {
      setReviewStatus("Select a signal or enter a ticker before submitting the review.");
      return;
    }
    if (Object.values(review).some((answer) => answer === null)) {
      setReviewStatus("Answer every checklist question before submitting the review.");
      return;
    }
    setLoadingReview(true);
    setReviewStatus(null);
    try {
      const created = await userApi.submitSignalReview({
        signal_id: selectedSignal?.id ?? null,
        ticker: reviewTicker,
        ...review,
        setup_confidence: reviewConfidence,
        notes: reviewNotes || null,
      }) as ProfessionalSignalReview;
      setReviewRows((rows) => [created, ...rows]);
      setReview(defaultReview);
      setReviewConfidence(5);
      setReviewNotes("");
      setReviewStatus(`Professional review recorded for ${reviewTicker}.`);
    } catch (error) {
      setReviewStatus(error instanceof Error ? error.message : "The signal review could not be recorded.");
    } finally {
      setLoadingReview(false);
    }
  }

  const reviewQuestions: Array<[keyof ReviewAnswers, string]> = [
    ["would_take_setup", "Would you take this setup?"],
    ["entry_logical", "Is the entry logical?"],
    ["stop_structurally_correct", "Is the stop structurally correct?"],
    ["targets_realistic", "Are TP1 and TP2 realistic?"],
    ["relevant_context_missing", "Is relevant context missing?"],
    ["market_regime_makes_sense", "Does the market-regime label make sense?"],
  ];

  return (
    <div className="min-h-screen bg-slate-950 font-sans text-slate-100 lg:flex">
      <Sidebar activePage="feedback" onNavigate={onNavigate} />
      <div className="min-w-0 flex-1">
        <Header eyebrow="Professional trader private beta" title="Feedback & Signal Review" />
        <main className="mx-auto max-w-[96rem] space-y-6 p-5 sm:p-8">
          <section className="grid gap-6 2xl:grid-cols-2">
            <form onSubmit={submitFeedback} className="rounded-2xl border border-slate-800 bg-slate-900/50 p-5 sm:p-6">
              <h2 className="text-lg font-semibold text-white">Structured product feedback</h2>
              <p className="mt-2 text-sm leading-6 text-slate-400">Report decision context, data quality, risk, usability, or operational problems. Avoid including credentials or private account data.</p>
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <label className="text-sm text-slate-300">Page<select value={feedbackPage} onChange={(event) => setFeedbackPage(event.target.value)} className="mt-2 h-11 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-white">{pageOptions.map((page) => <option key={page}>{page}</option>)}</select></label>
                <label className="text-sm text-slate-300">Ticker<input value={ticker} onChange={(event) => setTicker(event.target.value.toUpperCase())} maxLength={20} placeholder="Optional" className="mt-2 h-11 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-white placeholder:text-slate-600" /></label>
                <label className="text-sm text-slate-300">Category<select value={category} onChange={(event) => setCategory(event.target.value as FeedbackCategory)} className="mt-2 h-11 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-white">{categories.map((item) => <option key={item}>{item}</option>)}</select></label>
                <label className="text-sm text-slate-300">Severity<select value={severity} onChange={(event) => setSeverity(event.target.value as FeedbackSeverity)} className="mt-2 h-11 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-white">{severities.map((item) => <option key={item}>{item}</option>)}</select></label>
              </div>
              <label className="mt-4 block text-sm text-slate-300">Message<textarea value={message} onChange={(event) => setMessage(event.target.value)} minLength={10} maxLength={5000} required rows={6} placeholder="Describe what you observed, what you expected, and why it matters to a trader." className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 p-3 text-white placeholder:text-slate-600" /></label>
              <label className="mt-4 block text-sm text-slate-300">Screenshot reference<input value={screenshotReference} onChange={(event) => setScreenshotReference(event.target.value)} maxLength={500} placeholder="Optional filename or private reference" className="mt-2 h-11 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-white placeholder:text-slate-600" /></label>
              {feedbackStatus && <p className="mt-4 rounded-lg border border-cyan-400/20 bg-cyan-400/10 p-3 text-sm text-cyan-100">{feedbackStatus}</p>}
              <button disabled={loadingFeedback} className="mt-5 w-full rounded-lg bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:opacity-60">{loadingFeedback ? "Submitting…" : "Submit feedback"}</button>
            </form>

            <form onSubmit={submitReview} className="rounded-2xl border border-slate-800 bg-slate-900/50 p-5 sm:p-6">
              <h2 className="text-lg font-semibold text-white">Professional-trader signal checklist</h2>
              <p className="mt-2 text-sm leading-6 text-slate-400">Complete one review per inspected signal. Your answers assess the frozen setup; they do not modify its rules.</p>
              <label className="mt-5 block text-sm text-slate-300">Reviewed signal<select value={selectedSignalId} onChange={(event) => { setSelectedSignalId(event.target.value); const item = signals.find((signal) => signal.id === event.target.value); if (item) setTicker(item.ticker); }} className="mt-2 h-11 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-white"><option value="">Manual ticker review</option>{signals.map((signal) => <option key={signal.id} value={signal.id}>{signal.ticker} · {signal.signal_date} · {signal.sector}</option>)}</select></label>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {reviewQuestions.map(([key, label]) => <BinaryQuestion key={key} label={label} value={review[key]} onChange={(value) => setReview((current) => ({ ...current, [key]: value }))} />)}
              </div>
              <label className="mt-4 block text-sm text-slate-300">Confidence in the setup: <span className="font-semibold text-cyan-200">{reviewConfidence}/10</span><input type="range" min={1} max={10} value={reviewConfidence} onChange={(event) => setReviewConfidence(Number(event.target.value))} className="mt-3 w-full accent-cyan-400" /></label>
              <label className="mt-4 block text-sm text-slate-300">Notes<textarea value={reviewNotes} onChange={(event) => setReviewNotes(event.target.value)} maxLength={5000} rows={5} placeholder="Structural concerns, missing catalysts, liquidity, sector, or market context." className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 p-3 text-white placeholder:text-slate-600" /></label>
              {reviewStatus && <p className="mt-4 rounded-lg border border-cyan-400/20 bg-cyan-400/10 p-3 text-sm text-cyan-100">{reviewStatus}</p>}
              <button disabled={loadingReview} className="mt-5 w-full rounded-lg bg-emerald-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:opacity-60">{loadingReview ? "Submitting…" : "Submit signal review"}</button>
            </form>
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5"><h2 className="font-semibold text-white">Recent feedback</h2><div className="mt-4 space-y-3">{feedbackRows.slice(0, 5).map((item) => <article key={item.id} className="rounded-lg bg-slate-950/60 p-3"><div className="flex flex-wrap gap-2 text-xs"><span className="text-cyan-200">{item.category}</span><span className="text-slate-500">{item.severity}</span><span className="text-slate-500">{item.page}{item.ticker ? ` · ${item.ticker}` : ""}</span></div><p className="mt-2 text-sm text-slate-300">{item.message}</p></article>)}{feedbackRows.length === 0 && <p className="text-sm text-slate-500">No feedback submitted yet.</p>}</div></div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5"><h2 className="font-semibold text-white">Recent signal reviews</h2><div className="mt-4 space-y-3">{reviewRows.slice(0, 5).map((item) => <article key={item.id} className="rounded-lg bg-slate-950/60 p-3"><p className="text-sm font-semibold text-white">{item.ticker} · {item.setup_confidence}/10</p><p className="mt-1 text-xs text-slate-500">{item.would_take_setup ? "Would take setup" : "Would not take setup"} · {new Date(item.created_at).toLocaleString()}</p></article>)}{reviewRows.length === 0 && <p className="text-sm text-slate-500">No professional signal reviews submitted yet.</p>}</div></div>
          </section>
        </main>
      </div>
    </div>
  );
}
