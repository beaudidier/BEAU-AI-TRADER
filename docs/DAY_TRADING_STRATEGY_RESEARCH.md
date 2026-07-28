# Day Trading Strategy Research

## Scope and status

This document specifies two research candidates only:

1. Opening Range Breakout (ORB)
2. VWAP Pullback

It is a preregistered research specification, not a strategy recommendation or a
production implementation. The proposed work must use completed local
recordings through the existing deterministic replay path. It must not fetch,
backfill, or synthesize market data, and it must not change providers, the
recorder, replay engine, paper broker, shared APIs, or production code.

All session times below mean the regular US equity session in
`America/New_York`. Session boundaries must be converted to UTC for each
trading date with the applicable daylight-saving offset. Premarket and
after-hours events are excluded.

## Recorded-data fit

The repository currently contains two completed Alpaca IEX
`partial-market` recordings for the same trading date, 2026-07-27:

| Recording | Receipt-time coverage (UTC) | Accepted market events | Symbols |
| --- | --- | --- | --- |
| `20260727T160703Z-1e866d40` | 16:07:03–16:09:27 | 80,017 quotes; 970 trades; 20 one-minute bars | AAPL, AMD, AMZN, META, MSFT, NVDA, PLTR, QQQ, SPY, TSLA |
| `20260727T160949Z-f3997392` | 16:09:49–16:39:54 | 1,176,280 quotes; 16,473 trades; 299 one-minute bars | Same ten symbols |

The first recording has two one-minute bars per symbol (16:07–16:08 UTC).
The second generally has 30 per symbol (16:09–16:38 UTC; QQQ has 29). These
recordings begin well after the 09:30 New York open and do not contain the
opening range or the cumulative regular-session history required to calculate
session VWAP. They therefore provide **zero eligible symbol-sessions** for
either strategy under the rules below. They can exercise data parsing,
chronological event handling, and execution mechanics, but cannot support a
performance estimate or strategy comparison.

IEX coverage is a partial-market view. IEX volume and VWAP must not be
described as consolidated-market values, and results from IEX recordings must
not be mixed with recordings from another feed in the same result stratum.

## Common causal rules

- Only events with `disposition == "accepted"` are eligible.
- Signal calculations use closed one-minute bars only. A provider bar stamped
  at minute `t` becomes usable no earlier than its recorded receipt timestamp
  at or after `t + 1 minute`.
- Events are revealed in `(receipt_timestamp, index)` order. Provider
  timestamps describe market time but never authorize earlier availability.
- A decision made from the bar ending at `t` may submit an order only after
  that bar is available. It cannot fill from that bar or from an earlier event.
- Prices are not adjusted retrospectively. A symbol-session is excluded if a
  split or other discontinuity makes its recorded intraday series invalid and
  the recording itself does not contain a causally available adjustment.
- Each strategy permits at most one entry per symbol per regular session.
  Long and short rules are symmetric where stated. If long and short triggers
  become true on the same decision event, take neither.
- No position is held overnight. Cancel pending entries at 15:55 New York and
  flatten an open position using the first eligible exit execution at or after
  15:55.
- Risk unit `R = abs(entry fill price - initial stop price)`. Targets are based
  on the actual entry fill. If `R <= 0`, reject the trade.

## Strategy 1: Opening Range Breakout

### Required indicators

- Fifteen-minute opening range from the 15 closed one-minute bars stamped
  09:30 through 09:44:
  - `OR_high = max(high)`
  - `OR_low = min(low)`
  - `OR_width = OR_high - OR_low`
- Session VWAP, calculated causally from regular-session one-minute bars:
  `VWAP_t = sum(vwap_i * volume_i) / sum(volume_i)` from 09:30 through `t`.
  Use the recorded bar `vw` as `vwap_i`; if any required bar lacks `vw`, the
  symbol-session is ineligible.
- Breakout-bar volume and the median volume of the preceding 15 closed
  one-minute bars.

No ATR, daily history, gap statistic, or relative-volume baseline is required.

### Exact signal rules

Evaluate closed bars stamped 09:45 through 11:29 New York.

Long setup, all conditions required on the same closed decision bar:

1. All 15 opening-range bars are present, closed, and gap-free.
2. `OR_width > 0`.
3. The bar opens at or below `OR_high` and closes strictly above `OR_high`.
4. The bar closes strictly above its causal session VWAP.
5. Its volume is at least `1.5 * median(volume)` of the preceding 15 closed
   one-minute bars.

Short setup is the exact inverse:

1. The same opening-range integrity rules hold.
2. `OR_width > 0`.
3. The bar opens at or above `OR_low` and closes strictly below `OR_low`.
4. The bar closes strictly below its causal session VWAP.
5. The same `1.5x` volume condition holds.

The first qualifying decision bar is the only signal for that symbol-session.

### Entry, stop, and targets

- Entry: submit a market order at the decision bar's availability time. The
  order becomes executable only after the configured latency and fills using
  the first subsequent eligible event under the execution assumptions below.
- Long initial stop: `OR_low`. Short initial stop: `OR_high`.
- Reject an entry before submission if the decision-bar close is more than
  `1.0 * OR_width` beyond the breakout boundary; this prevents an already
  extended signal from creating an extreme stop distance.
- Target 1: exit 50% of the original quantity at `+1R`.
- Target 2: exit all remaining quantity at `+2R`.
- After Target 1 is completely filled, move the stop on the remainder to the
  actual entry fill price.
- If a stop and target are triggered by different recorded events, event order
  decides. If a single one-minute bar is the only available price evidence and
  its range crosses both levels with no tick evidence resolving the order,
  record the trade as ambiguous and exclude it from the primary result; report
  stop-first and target-first sensitivity results separately.

## Strategy 2: VWAP Pullback

### Required indicators

- Causal regular-session VWAP using the same formula and missing-`vw`
  eligibility rule as ORB.
- `EMA9_t = alpha * close_t + (1 - alpha) * EMA9_(t-1)`, where
  `alpha = 2 / (9 + 1)`. Seed EMA9 with the 09:30 close and update only on
  closed bars.
- `ATR14` using Wilder smoothing:
  - `TR_t = max(high_t - low_t, abs(high_t - close_(t-1)),
    abs(low_t - close_(t-1)))`
  - seed with the arithmetic mean of the first 14 true ranges beginning at
    09:31; thereafter `ATR14_t = (13 * ATR14_(t-1) + TR_t) / 14`.
- The preceding 15 closed one-minute bars for trend persistence.

### Exact signal rules

Evaluate closed bars stamped 10:00 through 15:29 New York.

Long setup, all conditions required:

1. Every regular-session one-minute bar from 09:30 through the decision bar is
   present, closed, and gap-free.
2. At least 12 of the 15 bars immediately preceding the decision bar closed
   strictly above their causal VWAP.
3. On the decision bar, `low <= VWAP`, `close > VWAP`, and `close > EMA9`.
   This defines a touch or penetration followed by a close reclaim.
4. The decision bar is bullish: `close > open`.
5. `ATR14 > 0`.

Short setup is the exact inverse:

1. The same history-integrity rule holds.
2. At least 12 of the preceding 15 bars closed strictly below their causal
   VWAP.
3. On the decision bar, `high >= VWAP`, `close < VWAP`, and `close < EMA9`.
4. The decision bar is bearish: `close < open`.
5. `ATR14 > 0`.

The first qualifying decision bar is the only signal for that symbol-session.

### Entry, stop, and targets

- Entry: submit a market order at the decision bar's availability time, with
  the same next-eligible-event constraint as ORB.
- Long initial stop:
  `min(decision_bar.low, VWAP_at_decision - 0.25 * ATR14_at_decision)`.
- Short initial stop:
  `max(decision_bar.high, VWAP_at_decision + 0.25 * ATR14_at_decision)`.
- Reject before submission if the initial risk exceeds
  `1.5 * ATR14_at_decision`.
- Target 1: exit 50% of original quantity at `+1R`.
- Target 2: exit all remaining quantity at `+2R`.
- Move the remaining stop to the actual entry fill after Target 1 completely
  fills.
- Apply the same event-order and ambiguous-bar policy as ORB.

## Look-ahead and selection risks

- **Bar completion:** using the high, low, close, volume, or VWAP of a minute
  before its receipt after minute-end leaks future information.
- **Provider versus receipt time:** sorting only by provider time can expose
  delayed events before they were recorded. Replay ordering must use receipt
  time and recorded index.
- **Session VWAP truncation:** initializing VWAP when a recording starts after
  09:30 produces a different indicator and is prohibited.
- **Opening-range truncation:** reconstructing the 09:30–09:44 range from
  later bars, partial bars, quotes, or external data is prohibited.
- **Aggregation leakage:** a derived five- or fifteen-minute bar is unavailable
  until every constituent minute is closed and received.
- **Intrabar ordering:** OHLC bars do not reveal whether a stop or target was
  reached first. Tick evidence may resolve this only when it was actually
  recorded and accepted.
- **VWAP substitution:** a close or typical price is not a permissible silent
  substitute for missing recorded bar VWAP.
- **Universe selection:** selecting symbols because their later moves are
  known creates survivorship/selection bias. Use the symbol list stored at
  recording start, frozen before replay outcomes are inspected.
- **Parameter tuning:** changing the opening-range length, volume multiple,
  trend count, ATR buffer, time windows, stops, or targets after viewing test
  results invalidates a holdout. Variants require a new, explicitly versioned
  experiment.
- **Cross-session contamination:** EMA, ATR, VWAP, positions, and per-session
  trade limits reset at each regular-session open.
- **Feed bias:** partial-market IEX prints, quotes, volume, and VWAP are not
  equivalent to consolidated data. Feed type must remain visible in every
  result.

## Execution assumptions

- Research is local and paper-only. No live order routing is permitted.
- Default simulation inputs mirror the existing replay execution model:
  100 ms order latency, 2 basis points adverse slippage, and a quote considered
  stale after 15 seconds.
- Market buys reference the latest non-stale ask; market sells reference the
  latest non-stale bid. Adverse slippage is then applied.
- An order submitted from a closed-bar signal cannot consume a trade or quote
  whose receipt time precedes its latency-adjusted eligibility time.
- Stop orders trigger only on a subsequent accepted trade at or through the
  stop. Profit-taking limit orders require a subsequent accepted trade at or
  through the limit and a non-stale quote.
- Available accepted trade size caps each fill, so partial fills are retained.
  Unfilled residual quantity remains working until filled, stopped, cancelled
  at 15:55, or the recording ends.
- Entry quantity is normalized to one unit for primary strategy comparison.
  Report returns in `R` and basis points; do not infer portfolio capacity from
  partial-market recordings.
- Commissions, exchange fees, borrow fees, locate availability, halts, and
  queue position are not represented by current recordings/replay. Primary
  results must state that these costs are excluded. Short results are
  hypothetical unless borrow availability was recorded, which it currently is
  not.
- A recording that ends while an order or position is open is censored, not
  treated as a profitable, losing, or flat exit.

## Minimum data requirements

A symbol-session is eligible only when all of the following hold:

- A completed recording covers continuously from no later than 09:30 through
  at least 15:55 New York for exit accounting.
- Accepted, closed one-minute bars are gap-free from 09:30 through the final
  decision/exit event used by the trade.
- Every required bar contains open, high, low, close, volume, and provider
  VWAP.
- Accepted quotes cover every order submission and fill, with a valid
  `0 < bid <= ask` and age no greater than 15 seconds.
- Accepted trades are present for stop/limit triggers and liquidity-capped
  fills.
- Receipt timestamp, provider timestamp, event index, symbol, source,
  coverage, disposition, and payload are retained.
- The recording includes the frozen symbol universe and feed/coverage label.

For a performance study rather than a plumbing check, require at minimum 30
eligible regular sessions per feed stratum and at least 30 completed trades per
strategy side (long and short reported separately). These are reporting
thresholds, not claims of statistical sufficiency. If they are not met, report
descriptive counts only and make no comparative conclusion.

The current two recordings fail the full-session and gap-free-from-open
requirements, so the proposed backtest must initially report zero eligible
sessions and no performance statistics.

## Proposed backtest plan

1. **Freeze the specification.** Hash this document and record the commit,
   strategy identifier (`orb_v1` or `vwap_pullback_v1`), feed, and execution
   parameters with every run.
2. **Inventory local recordings.** Enumerate completed recordings only; verify
   their checksums and deterministic replay digests. Do not download or
   augment data.
3. **Run an eligibility audit before signals.** For each recording and
   symbol-session, report session coverage, missing/incomplete minutes,
   missing VWAP values, stale-quote intervals, accepted trade/quote counts,
   and exclusion reasons. The current corpus should yield zero eligible
   symbol-sessions.
4. **Replay causally.** Reveal accepted events in receipt-time/index order,
   update indicators only when a closed bar becomes available, and emit an
   immutable decision ledger containing all indicator inputs and failed/passed
   predicates for every evaluated bar.
5. **Simulate orders.** Apply the fixed latency, quote freshness, bid/ask,
   trade-through, partial-fill, slippage, stop/target, ambiguity, cancellation,
   and end-of-day rules above.
6. **Verify determinism.** Run each eligible recording at least three times.
   Event, signal, order, fill, and result digests must match exactly.
7. **Split chronologically when enough recordings exist.** Use the earliest
   60% of eligible sessions as development, the next 20% as validation, and
   lock the final 20% as holdout. Split by trading date, never by symbol-row.
   Do not inspect holdout outcomes until code and parameters are frozen.
8. **Report without recommendations.** For each strategy, side, feed, and
   split, report eligible sessions, signals, entries, fill rate, censored and
   ambiguous trades, win rate, mean/median `R`, total `R`, basis-point return,
   maximum drawdown in `R`, profit factor, average adverse/favorable excursion,
   holding time, slippage, and stale/rejected-order counts. Include the
   no-slippage and 5 bps slippage cases as labeled execution sensitivity, not
   parameter selection.
9. **Preserve null results.** Zero-signal and zero-eligible-session runs are
   valid outputs. Do not relax rules, impute missing opening data, or merge
   strategies to manufacture a comparison.
