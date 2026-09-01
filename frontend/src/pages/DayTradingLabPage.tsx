import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import DayTradingChart from "../components/DayTradingChart";
import Header from "../components/Header";
import Sidebar, { type AppPage } from "../components/Sidebar";
import { DAY_TRADING_LAB_ENABLED } from "../config";
import { dayTradingApi } from "../services/dayTradingApi";
import type {
  DayTradingBars,
  DayTradingQuote,
  DayTradingStatus,
  DayTradingTimeframe,
  PaperAccount,
  PaperPositions,
  RecordingSession,
  RecordingStatus,
  ReplayStatus,
} from "../types/dayTrading";

type DayTradingLabPageProps = { onNavigate: (page: AppPage) => void };

function money(value?: number) {
  return value == null || !Number.isFinite(value) ? "—" : `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function dateTime(value?: string | null) {
  if (!value) return "Not available";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "Not available" : parsed.toLocaleString();
}

function DayTradingLabPage({ onNavigate }: DayTradingLabPageProps) {
  const [status, setStatus] = useState<DayTradingStatus | null>(null);
  const [quote, setQuote] = useState<DayTradingQuote | null>(null);
  const [bars, setBars] = useState<DayTradingBars | null>(null);
  const [account, setAccount] = useState<PaperAccount | null>(null);
  const [positions, setPositions] = useState<PaperPositions | null>(null);
  const [recording, setRecording] = useState<RecordingStatus | null>(null);
  const [recordings, setRecordings] = useState<RecordingSession[]>([]);
  const [replay, setReplay] = useState<ReplayStatus | null>(null);
  const [replayBars, setReplayBars] = useState<DayTradingBars | null>(null);
  const [replayTimeframe, setReplayTimeframe] = useState<DayTradingTimeframe>("1m");
  const [selectedRecording, setSelectedRecording] = useState("");
  const [replaySpeed, setReplaySpeed] = useState<ReplayStatus["speed"]>("maximum");
  const [seekTimestamp, setSeekTimestamp] = useState("");
  const [tickerInput, setTickerInput] = useState("AAPL");
  const [ticker, setTicker] = useState("AAPL");
  const [timeframe, setTimeframe] = useState<DayTradingTimeframe>("1m");
  const [orderType, setOrderType] = useState<"market" | "limit" | "stop">("market");
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [quantity, setQuantity] = useState("1");
  const [limitPrice, setLimitPrice] = useState("");
  const [triggerPrice, setTriggerPrice] = useState("");
  const [protectiveStop, setProtectiveStop] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const requestKey = useRef<string | null>(null);

  const load = useCallback(async (quiet = false) => {
    if (!DAY_TRADING_LAB_ENABLED) return;
    if (!quiet) setLoading(true);
    const settled = await Promise.allSettled([
      dayTradingApi.status(),
      dayTradingApi.quote(ticker),
      dayTradingApi.bars(ticker, timeframe),
      dayTradingApi.paperAccount(),
      dayTradingApi.paperPositions(),
      dayTradingApi.recordingStatus(),
      dayTradingApi.recordingSessions(),
      dayTradingApi.replayStatus(),
      dayTradingApi.replayBars(ticker, replayTimeframe),
    ]);
    if (settled[0].status === "fulfilled") setStatus(settled[0].value);
    if (settled[1].status === "fulfilled") setQuote(settled[1].value);
    if (settled[2].status === "fulfilled") setBars(settled[2].value);
    if (settled[3].status === "fulfilled") setAccount(settled[3].value);
    if (settled[4].status === "fulfilled") setPositions(settled[4].value);
    if (settled[5].status === "fulfilled") setRecording(settled[5].value);
    const sessionsResult = settled[6];
    if (sessionsResult.status === "fulfilled") {
      const availableSessions = sessionsResult.value.sessions;
      setRecordings(availableSessions);
      setSelectedRecording((current) => current || availableSessions[0]?.session_id || "");
    }
    if (settled[7].status === "fulfilled") setReplay(settled[7].value);
    if (settled[8].status === "fulfilled") setReplayBars(settled[8].value);
    const failed = settled.filter((result) => result.status === "rejected");
    setError(failed.length ? "Some local Alpaca data is unavailable. Previous valid values remain visible." : null);
    if (!quiet) setLoading(false);
  }, [ticker, timeframe, replayTimeframe]);

  useEffect(() => {
    void load();
    const interval = window.setInterval(() => void load(true), 3_000);
    return () => window.clearInterval(interval);
  }, [load]);

  const blockedReason = useMemo(() => {
    if (!account?.paper_orders_enabled) return "Paper orders are disabled by the emergency switch.";
    if (status?.market_clock.status !== "regular") return "Orders are accepted only during the regular US session.";
    if (!quote) return "A current quote is required.";
    if (quote.stale) return "The quote is stale. Wait for a current quote.";
    if (status && quote.spread_percent > status.risk_controls.maximum_spread_percent) return "The bid/ask spread is above the configured limit.";
    if (account?.daily_loss_locked) return "The daily paper-loss limit has been reached.";
    if (side === "buy" && !protectiveStop) return "A protective stop is required.";
    return null;
  }, [account, protectiveStop, quote, side, status]);

  function selectTicker() {
    const next = tickerInput.trim().toUpperCase();
    if (!/^[A-Z][A-Z0-9.-]{0,9}$/.test(next)) {
      setError("Enter a valid US stock ticker.");
      return;
    }
    requestKey.current = null;
    setTicker(next);
    setError(null);
  }

  async function submitOrder() {
    if (blockedReason || submitting) return;
    setSubmitting(true);
    setError(null);
    setNotice(null);
    requestKey.current ??= crypto.randomUUID();
    try {
      await dayTradingApi.submitOrder({
        ticker,
        side,
        order_type: orderType,
        quantity: Number(quantity),
        idempotency_key: requestKey.current,
        ...(orderType === "limit" ? { limit_price: Number(limitPrice) } : {}),
        ...(orderType === "stop" ? { stop_price: Number(triggerPrice) } : {}),
        ...(side === "buy" ? { protective_stop: Number(protectiveStop) } : {}),
      });
      setNotice("Paper order accepted. No live-money order was sent.");
      requestKey.current = null;
      await load(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The paper order was not accepted.");
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleOrders() {
    if (!account) return;
    setSubmitting(true);
    try {
      await dayTradingApi.setOrdersEnabled(!account.paper_orders_enabled);
      await load(true);
    } catch {
      setError("The emergency paper-order control could not be changed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleRecording() {
    setSubmitting(true);
    setError(null);
    try {
      if (recording?.active) {
        await dayTradingApi.stopRecording();
        setNotice("Recording stopped and checksum metadata was finalized.");
      } else {
        await dayTradingApi.startRecording();
        setNotice("Append-only IEX recording started for the configured symbols.");
      }
      await load(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The recorder could not be changed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function startReplay() {
    if (!selectedRecording) return;
    setSubmitting(true);
    setError(null);
    try {
      setReplay(await dayTradingApi.startReplay(selectedRecording, replaySpeed));
      setNotice("Deterministic local replay started. No Alpaca order can be routed.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The replay could not start.");
    } finally {
      setSubmitting(false);
    }
  }

  async function controlReplay(action: "pause" | "resume" | "reset") {
    setSubmitting(true);
    try {
      const result = action === "pause" ? await dayTradingApi.pauseReplay() : action === "resume" ? await dayTradingApi.resumeReplay() : await dayTradingApi.resetReplay();
      setReplay(result);
    } catch {
      setError("The replay control could not be changed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function seekReplay() {
    if (!seekTimestamp) return;
    setSubmitting(true);
    try {
      setReplay(await dayTradingApi.seekReplay(new Date(seekTimestamp).toISOString()));
    } catch {
      setError("The replay timestamp could not be selected.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!DAY_TRADING_LAB_ENABLED) {
    return <div className="min-h-screen bg-slate-950 text-slate-100 lg:flex">
      <Sidebar activePage="day-trading-lab" onNavigate={onNavigate} />
      <div className="min-w-0 flex-1"><Header eyebrow="Local and staging only" title="Day Trading Lab" /><main className="p-8"><div className="rounded-xl border border-amber-400/30 bg-amber-400/10 p-6 text-amber-100">The Day Trading Lab is disabled in this environment.</div></main></div>
    </div>;
  }

  return <div className="min-h-screen bg-slate-950 text-slate-100 lg:flex">
    <Sidebar activePage="day-trading-lab" onNavigate={onNavigate} />
    <div className="min-w-0 flex-1">
      <Header eyebrow="Local/staging · paper only" title="Day Trading Lab" />
      <main className="mx-auto max-w-[1600px] space-y-5 p-5 sm:p-8">
        <section className="rounded-xl border border-rose-400/30 bg-rose-400/10 p-4">
          <p className="font-semibold text-rose-100">Paper trading only. No real-money execution. No AI recommendations.</p>
          <p className="mt-1 text-sm text-rose-100/75">Alpaca IEX is a single-exchange development feed with partial US-market coverage. It must never be treated as the complete market.</p>
        </section>

        {error && <div className="flex items-center justify-between gap-4 rounded-xl border border-amber-400/30 bg-amber-400/10 p-4 text-sm text-amber-100"><span>{error}</span><button type="button" onClick={() => void load()} className="rounded-lg border border-amber-300/30 px-3 py-1.5 font-semibold">Retry</button></div>}
        {notice && <div className="rounded-xl border border-emerald-400/30 bg-emerald-400/10 p-4 text-sm text-emerald-100">{notice}</div>}

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {[
            ["Market", status?.market_clock.status ?? "Unknown"],
            ["Data source", status?.provider.source ?? "Alpaca IEX"],
            ["Coverage", status?.provider.coverage ?? "partial-market"],
            ["Stream", status?.stream.state ?? "Unavailable"],
            ["Last event", dateTime(status?.stream.last_event_at)],
          ].map(([label, value]) => <div key={label} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"><p className="text-xs uppercase tracking-wider text-slate-500">{label}</p><p className="mt-2 truncate font-semibold capitalize text-white">{value}</p></div>)}
        </section>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1.7fr)_minmax(20rem,0.8fr)]">
          <div className="space-y-5">
            <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <form className="flex gap-2" onSubmit={(event) => { event.preventDefault(); selectTicker(); }}>
                  <input value={tickerInput} onChange={(event) => setTickerInput(event.target.value)} aria-label="US stock ticker" className="w-28 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-semibold uppercase outline-none focus:border-cyan-400" />
                  <button type="submit" className="rounded-lg bg-cyan-400 px-4 py-2 font-semibold text-slate-950">Load</button>
                </form>
                <div className="flex gap-2">{(["1m", "5m", "15m"] as DayTradingTimeframe[]).map((value) => <button key={value} type="button" onClick={() => setTimeframe(value)} className={`rounded-lg px-3 py-2 text-sm font-semibold ${timeframe === value ? "bg-cyan-400 text-slate-950" : "bg-slate-800 text-slate-300"}`}>{value}</button>)}</div>
              </div>
              <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-5">
                {[["Ticker", ticker], ["Mid", money(quote?.midpoint)], ["Bid", money(quote?.bid)], ["Ask", money(quote?.ask)], ["Spread", quote ? `${quote.spread_percent.toFixed(3)}%` : "—"]].map(([label, value]) => <div key={label}><p className="text-xs text-slate-500">{label}</p><p className="mt-1 font-semibold text-white">{value}</p></div>)}
              </div>
              <p className={`mt-3 text-xs ${quote?.stale ? "text-rose-300" : "text-slate-500"}`}>{quote?.stale ? "Stale quote — orders are blocked." : `Quote timestamp: ${dateTime(quote?.timestamp)}`}</p>
              <div className="mt-5 overflow-hidden rounded-lg border border-slate-800">{bars ? <DayTradingChart data={bars} /> : <div className="grid h-80 place-items-center text-sm text-slate-500">{loading ? "Loading intraday bars…" : "No bars available."}</div>}</div>
              <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500"><span>{bars?.bars.filter((bar) => bar.completeness === "closed").length ?? 0} closed bars</span><span>{bars?.bars.filter((bar) => bar.completeness !== "closed").length ?? 0} incomplete/gap bars</span><span>{bars?.gaps.length ?? 0} detected gaps</span></div>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
              <h2 className="text-lg font-semibold text-white">Open paper positions</h2>
              <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[36rem] text-left text-sm"><thead className="text-xs uppercase text-slate-500"><tr><th className="pb-3">Ticker</th><th className="pb-3">Quantity</th><th className="pb-3">Entry</th><th className="pb-3">Stop</th><th className="pb-3">Current</th><th className="pb-3">Unrealised P/L</th></tr></thead><tbody>{positions?.open.length ? positions.open.map((position) => <tr key={position.ticker} className="border-t border-slate-800"><td className="py-3 font-semibold text-white">{position.ticker}</td><td>{position.quantity}</td><td>{money(position.entry_price)}</td><td>{money(position.protective_stop)}</td><td>{money(position.current_price)}</td><td className={position.unrealized_pnl >= 0 ? "text-emerald-300" : "text-rose-300"}>{money(position.unrealized_pnl)}</td></tr>) : <tr><td colSpan={6} className="border-t border-slate-800 py-8 text-center text-slate-500">No open day-trading paper positions.</td></tr>}</tbody></table></div>
            </div>
          </div>

          <aside className="space-y-5">
            <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
              <div className="flex items-start justify-between gap-4"><div><p className="text-xs uppercase tracking-wider text-slate-500">Paper account</p><p className="mt-2 text-2xl font-semibold text-white">{money(account?.equity)}</p></div><span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2.5 py-1 text-xs font-semibold text-cyan-300">SIMULATED</span></div>
              <dl className="mt-5 space-y-3 text-sm">{[["Cash", money(account?.cash)], ["Daily P/L", money(account?.daily_pnl)], ["Open positions", `${account?.open_positions ?? 0} / ${account?.maximum_open_positions ?? 2}`], ["Risk per trade", `${account?.maximum_risk_per_trade_percent ?? 0.25}%`], ["Daily loss limit", `${account?.maximum_daily_loss_percent ?? 0.5}%`]].map(([label, value]) => <div key={label} className="flex justify-between gap-4"><dt className="text-slate-500">{label}</dt><dd className="font-medium text-slate-200">{value}</dd></div>)}</dl>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
              <h2 className="text-lg font-semibold text-white">Paper order ticket</h2>
              <div className="mt-4 grid grid-cols-2 gap-3"><label className="text-sm text-slate-400">Side<select value={side} onChange={(event) => { setSide(event.target.value as "buy" | "sell"); requestKey.current = null; }} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"><option value="buy">Buy</option><option value="sell">Sell to close</option></select></label><label className="text-sm text-slate-400">Type<select value={orderType} onChange={(event) => { setOrderType(event.target.value as "market" | "limit" | "stop"); requestKey.current = null; }} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"><option value="market">Market</option><option value="limit">Limit</option><option value="stop">Stop</option></select></label></div>
              <label className="mt-3 block text-sm text-slate-400">Quantity<input type="number" min="1" value={quantity} onChange={(event) => { setQuantity(event.target.value); requestKey.current = null; }} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white" /></label>
              {orderType === "limit" && <label className="mt-3 block text-sm text-slate-400">Limit price<input type="number" min="0.01" step="0.01" value={limitPrice} onChange={(event) => { setLimitPrice(event.target.value); requestKey.current = null; }} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white" /></label>}
              {orderType === "stop" && <label className="mt-3 block text-sm text-slate-400">Trigger price<input type="number" min="0.01" step="0.01" value={triggerPrice} onChange={(event) => { setTriggerPrice(event.target.value); requestKey.current = null; }} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white" /></label>}
              {side === "buy" && <label className="mt-3 block text-sm text-slate-400">Protective stop<input type="number" min="0.01" step="0.01" value={protectiveStop} onChange={(event) => { setProtectiveStop(event.target.value); requestKey.current = null; }} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white" /></label>}
              {blockedReason && <p className="mt-3 rounded-lg bg-amber-400/10 p-3 text-xs leading-5 text-amber-200">{blockedReason}</p>}
              <button type="button" onClick={() => void submitOrder()} disabled={Boolean(blockedReason) || submitting || Number(quantity) <= 0} className="mt-4 w-full rounded-lg bg-cyan-400 px-4 py-3 font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-40">{submitting ? "Submitting…" : "Submit simulated order"}</button>
            </div>

            <div className="rounded-xl border border-rose-400/30 bg-rose-400/5 p-5"><div className="flex items-center justify-between gap-4"><div><p className="font-semibold text-rose-100">Emergency paper-order control</p><p className="mt-1 text-xs leading-5 text-rose-100/65">Disabling blocks new simulated orders. It does not create or route any brokerage order.</p></div><button type="button" role="switch" aria-checked={!account?.paper_orders_enabled} onClick={() => void toggleOrders()} disabled={!account || submitting} className={`relative h-7 w-12 shrink-0 rounded-full transition ${account?.paper_orders_enabled ? "bg-slate-700" : "bg-rose-500"}`}><span className={`absolute top-1 size-5 rounded-full bg-white transition ${account?.paper_orders_enabled ? "left-1" : "left-6"}`} /></button></div></div>
          </aside>
        </section>

        <section className="rounded-xl border border-violet-400/20 bg-slate-900/60 p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-violet-300">Local research only</p>
              <h2 className="mt-2 text-xl font-semibold text-white">Intraday recorder and deterministic replay</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">Raw Alpaca IEX events are stored append-only in compressed, checksummed local files. Replay never touches production data or routes any paper or live brokerage order.</p>
            </div>
            <button type="button" onClick={() => void toggleRecording()} disabled={submitting} className={`rounded-lg px-4 py-2.5 text-sm font-semibold ${recording?.active ? "bg-rose-400 text-slate-950" : "bg-violet-400 text-slate-950"} disabled:opacity-40`}>{recording?.active ? "Stop recording" : "Start recording"}</button>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            {[
              ["Recorder", recording?.active ? "Recording" : recording?.status ?? "Idle"],
              ["Raw events", (recording?.event_count ?? 0).toLocaleString()],
              ["Symbols", recording?.symbols?.length?.toString() ?? "—"],
              ["Coverage", recording?.coverage ?? "partial-market"],
              ["Data gaps", recording?.gaps?.length?.toString() ?? "0"],
            ].map(([label, value]) => <div key={label} className="rounded-lg border border-slate-800 bg-slate-950/60 p-3"><p className="text-xs uppercase tracking-wide text-slate-500">{label}</p><p className="mt-2 font-semibold capitalize text-white">{value}</p></div>)}
          </div>

          <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_auto_auto]">
            <label className="text-sm text-slate-400">Recorded session<select value={selectedRecording} onChange={(event) => setSelectedRecording(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"><option value="">Select a completed session</option>{recordings.filter((session) => session.status === "completed").map((session) => <option key={session.session_id} value={session.session_id}>{session.session_id} · {session.event_count.toLocaleString()} events</option>)}</select></label>
            <label className="text-sm text-slate-400">Replay speed<select value={replaySpeed} onChange={(event) => setReplaySpeed(event.target.value as ReplayStatus["speed"])} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"><option value="original">Original</option><option value="10x">10×</option><option value="maximum">Maximum deterministic</option></select></label>
            <button type="button" onClick={() => void startReplay()} disabled={!selectedRecording || submitting} className="self-end rounded-lg bg-cyan-400 px-4 py-2 font-semibold text-slate-950 disabled:opacity-40">Start replay</button>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => void controlReplay("pause")} disabled={replay?.status !== "running" || submitting} className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-semibold text-slate-300 disabled:opacity-40">Pause</button>
            <button type="button" onClick={() => void controlReplay("resume")} disabled={replay?.status !== "paused" || submitting} className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-semibold text-slate-300 disabled:opacity-40">Resume</button>
            <button type="button" onClick={() => void controlReplay("reset")} disabled={!replay?.session_id || submitting} className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-semibold text-slate-300 disabled:opacity-40">Reset</button>
            <input type="datetime-local" value={seekTimestamp} onChange={(event) => setSeekTimestamp(event.target.value)} aria-label="Replay seek timestamp" className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200" />
            <button type="button" onClick={() => void seekReplay()} disabled={!replay?.session_id || !seekTimestamp || submitting} className="rounded-lg border border-violet-400/40 px-3 py-2 text-sm font-semibold text-violet-200 disabled:opacity-40">Seek</button>
            <span className="ml-auto text-sm text-slate-400">{replay?.status ?? "idle"} · {replay?.progress_percent ?? 0}% · {dateTime(replay?.current_replay_timestamp)}</span>
          </div>

          <div className="mt-5 grid gap-4 lg:grid-cols-3">
            <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4"><p className="text-xs uppercase tracking-wide text-slate-500">Replay quote</p><p className="mt-2 text-sm text-slate-200">{ticker} bid {money(replay?.quotes[ticker]?.bid)} · ask {money(replay?.quotes[ticker]?.ask)} · spread {replay?.quotes[ticker] ? `${replay.quotes[ticker].spread_percent.toFixed(3)}%` : "—"}</p></div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4"><p className="text-xs uppercase tracking-wide text-slate-500">Simulated orders</p><p className="mt-2 text-sm text-slate-200">{replay?.simulated_orders.length ?? 0} orders · {replay?.simulated_fills.length ?? 0} fill legs</p></div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4"><p className="text-xs uppercase tracking-wide text-slate-500">Data quality and safety</p><p className="mt-2 text-sm text-emerald-300">{recording?.gaps?.length ?? 0} gaps · paper-only replay · live routing disabled</p>{replay?.error && <p className="mt-2 text-xs text-rose-300">{replay.error}</p>}</div>
          </div>

          <div className="mt-5 rounded-lg border border-slate-800 bg-slate-950/40 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="font-semibold text-white">Replayed {ticker} bars</p>
              <div className="flex gap-2">{(["1m", "5m", "15m"] as DayTradingTimeframe[]).map((value) => <button key={value} type="button" onClick={() => setReplayTimeframe(value)} className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${replayTimeframe === value ? "bg-violet-400 text-slate-950" : "bg-slate-800 text-slate-300"}`}>{value}</button>)}</div>
            </div>
            <div className="mt-4 overflow-hidden rounded-lg border border-slate-800">{replayBars?.bars.length ? <DayTradingChart data={replayBars} /> : <div className="grid h-64 place-items-center text-sm text-slate-500">Start or seek a completed replay to display deterministic bars.</div>}</div>
          </div>

          {(replay?.simulated_orders.length || replay?.simulated_fills.length) ? <div className="mt-5 overflow-x-auto"><table className="w-full min-w-[42rem] text-left text-sm"><thead className="text-xs uppercase text-slate-500"><tr><th className="pb-3">Type</th><th className="pb-3">Symbol</th><th className="pb-3">Status/time</th><th className="pb-3">Quantity</th><th className="pb-3">Price</th></tr></thead><tbody>{replay.simulated_orders.map((order) => <tr key={order.id} className="border-t border-slate-800"><td className="py-3 text-violet-300">Order</td><td>{order.symbol}</td><td>{order.status}</td><td>{order.filled_quantity} / {order.filled_quantity + order.remaining}</td><td>—</td></tr>)}{replay.simulated_fills.map((fill) => <tr key={`${fill.order_id}-${fill.timestamp}`} className="border-t border-slate-800"><td className="py-3 text-cyan-300">Fill</td><td>{fill.symbol}</td><td>{dateTime(fill.timestamp)}</td><td>{fill.quantity}</td><td>{money(fill.price)}</td></tr>)}</tbody></table></div> : null}
        </section>
      </main>
    </div>
  </div>;
}

export default DayTradingLabPage;
