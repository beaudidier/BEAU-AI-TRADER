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

For a performance study rather than a plumbing check, use the stricter sample
thresholds in the Data Acceptance Specification below. If they are not met,
report operational and descriptive counts only and make no performance claim
or comparative conclusion.

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

## Data Acceptance Specification

This section defines the recordings that must exist before either strategy may
be coded or tested. It is a data contract, not authorization to change the
recorder or acquire external data. A future acquisition milestone must satisfy
the contract using completed local recordings and must keep every feed stratum
separate.

### Shared recording windows

Each candidate trading date must be one continuous recording in New York local
market time:

| Segment | Required coverage | Purpose |
| --- | --- | --- |
| Premarket | 04:00:00–09:29:59 | Premarket high/low, gap context, liquidity, and transition into the open |
| Regular open | 09:30:00–10:00:00 | Complete 5-, 15-, and 30-minute opening ranges |
| Midday | 10:00:01–15:29:59 | VWAP history and pullback candidates |
| Close | 15:30:00–16:00:00 | End-of-day exits and closing-liquidity behavior |
| After-hours | 16:00:01–20:00:00 | Boundary validation only; never a strategy entry window |

The recorder must be running and healthy by 04:00:00. For both strategies,
the first mandatory calculation input is the 09:30 bar. A start after 09:30:00
makes that symbol-session ineligible even if later data is complete.

Every event needed for validation must retain:

- receipt timestamp with subsecond precision;
- provider timestamp with subsecond precision;
- stable recorded index and provider sequence where available;
- symbol, event type, disposition, source, and coverage mode;
- quote bid, ask, bid size, ask size, exchange, and conditions;
- trade price, size, exchange, tape, and conditions;
- one-minute bar open, high, low, close, volume, provider VWAP, timestamp, and
  completeness;
- disconnect, reconnect, heartbeat, market-clock, gap, and recovery events.

### Shared liquidity and spread eligibility

Calculate these filters from causally available accepted IEX events. They
describe IEX-observed liquidity only:

- The time-weighted quoted spread from 09:30 through the entry decision must
  have a median no greater than 20 basis points.
- At least 95% of regular-session seconds from 09:30 through the decision must
  have a valid quote no older than 15 seconds. Any continuous stale interval
  longer than 30 seconds is an exclusion.
- Median accepted one-minute dollar volume from 09:30 through the decision,
  calculated as `bar.vwap * bar.volume`, must be at least USD 100,000.
- At least one accepted trade must occur in 90% of the closed one-minute bars
  from 09:30 through the decision. A bar supplied by the provider without an
  accepted local trade is retained for bar validation but does not satisfy
  this trade-activity filter.
- At entry time the current spread must be no greater than both 20 basis points
  and `0.10R`. If either test fails, the signal is logged but not tradable.

Do not tune these thresholds after inspecting returns. A different threshold
is a separately versioned experiment.

### Opening Range Breakout data contract

#### Required time coverage and range windows

- Premarket recording must start no later than 04:00:00 New York.
- Regular-session recording must include every closed minute from 09:30 onward.
- Persist exact, independently auditable range values for:
  - OR5: bars stamped 09:30–09:34;
  - OR15: bars stamped 09:30–09:44;
  - OR30: bars stamped 09:30–09:59.
- `high`, `low`, `width`, constituent timestamps, completeness, and the receipt
  time at which each range became available must be recorded in the research
  ledger.
- OR15 remains the preregistered primary rule in this document. OR5 and OR30
  are data-sufficiency checks and may be tested only as separately named,
  frozen variants; they cannot be selected after comparing their returns.

#### Gap handling

Define:

`gap_percent = (regular_open_09:30 - prior_regular_close_16:00) /
prior_regular_close_16:00 * 100`.

- The prior close must come from an eligible local recording of the immediately
  preceding trading session and the same feed. Do not fetch or impute it.
- Classify `gap_up` when `gap_percent >= +0.50%`, `gap_down` when
  `gap_percent <= -0.50%`, and `flat_gap` otherwise.
- Gap class is a reporting stratum, not an entry filter for `orb_v1`.
- If the prior close or 09:30 open is missing, label the gap `unknown`; the
  session may test OR mechanics but is excluded from gap-stratified results.

#### Halts and corporate actions

- Reject a symbol-session if a regulatory halt, limit-up/limit-down state, or
  unexplained interval with no valid quotes and trades overlaps 09:30–11:30.
- A halt is validly identified only by a recorded status event or by provider
  metadata explicitly marking it. Silence alone is an unexplained gap.
- Reject the entire symbol-date when a split, reverse split, symbol change,
  cash/stock distribution, or other price-basis-changing action is effective
  and its adjustment metadata is not contained in the local recorded dataset.
- Never infer an adjustment from future prices or repair it with current
  external reference data. Corporate-action exclusions and reasons must be
  reported.

#### ORB-specific fields and minimum data

In addition to shared fields, ORB requires:

- complete OHLCV and provider VWAP for every opening-range and decision bar;
- accepted quotes and trades spanning every boundary crossing;
- the last valid premarket quote and trade before 09:30;
- the exact quote, spread, trade, and receipt time used for each simulated
  entry, stop, and target;
- bar and trade condition codes needed to explain provider-bar differences.

Before any ORB performance claim, require all of:

- at least 60 eligible complete regular sessions spanning at least 12 calendar
  weeks;
- at least 20 symbols present throughout the study;
- at least 5 sectors, with no sector contributing more than 35% of eligible
  symbol-sessions or completed trades;
- at least 15 sessions in each realized SPY regime defined below;
- at least 100 completed ORB trades in total and at least 40 completed trades
  on each reported side;
- at least 30 completed trades in each gap class for any gap-stratified claim.

### VWAP Pullback data contract

#### Exact session VWAP and reset

VWAP resets exactly at 09:30:00 New York on every regular trading date. No
premarket or prior-session price or volume enters the strategy VWAP.

For closed one-minute bar `i`:

`bar_notional_i = recorded_provider_vwap_i * recorded_volume_i`

`session_VWAP_t = sum(bar_notional_i, 09:30..t) /
sum(recorded_volume_i, 09:30..t)`.

- Use only accepted, closed, gap-free one-minute bars known by receipt time.
- Provider bar VWAP and volume are required; close, midpoint, typical price,
  quote size, or locally observed trade notional may not silently replace them.
- Premarket volume is retained for diagnostics but excluded from both numerator
  and denominator.
- The cumulative numerator, denominator, VWAP, last included bar timestamp,
  and calculation availability time must be written to the decision ledger.
- Reset cumulative values at every regular open, including after holidays,
  weekends, early closes, and daylight-saving changes.

#### Missing and sparse trade handling

- Any missing, incomplete, duplicate-only, or unexplained regular-session bar
  from 09:30 through the decision invalidates the VWAP for the remainder of
  that symbol-session.
- A provider bar with volume but no accepted local IEX trade is a
  provider/local discrepancy. Do not reconstruct its hidden prints. The bar
  may remain in an integrity report, but the symbol-session fails the
  trade-activity filter unless the absence is explicitly explained by recorded
  provider conditions.
- For each minute compare provider bar close and VWAP with accepted trade
  prices, and compare provider volume with summed accepted trade size. Record
  differences; do not require equality because the IEX bar construction and
  trade-condition eligibility may differ.
- A bar fails quote-versus-trade validation if every accepted trade price lies
  outside the contemporaneous valid bid/ask envelope and no recorded condition
  explains it. Any unexplained failure before entry rejects the symbol-session.
- Sparse IEX activity is never filled from SIP, another provider, interpolation,
  or future data.

#### VWAP Pullback minimum data

The complete regular session from 09:30 through 16:00 is required, plus the
shared 04:00–20:00 boundary recording. A candidate pullback additionally
requires:

- gap-free VWAP inputs from 09:30 through its decision bar;
- at least 30 closed minutes before evaluation begins at 10:00;
- valid EMA9 and ATR14 inputs under the formulas above;
- compliance with every shared liquidity and spread filter;
- accepted quote/trade evidence for the VWAP touch or penetration, reclaim,
  entry, stop, and targets.

Before any VWAP Pullback performance claim, require all of:

- at least 60 eligible complete regular sessions spanning at least 12 calendar
  weeks;
- at least 20 symbols and 5 sectors under the same 35% concentration cap;
- at least 15 sessions in each realized SPY regime;
- at least 150 valid pullback signals before execution filtering;
- at least 100 completed trades in total and at least 40 completed trades on
  each reported side.

Signals rejected for spread, staleness, liquidity, or missing data count toward
the audit trail but not toward the 100 completed-trade threshold.

### Required market regimes and sectors

Regimes are labeled only after a complete SPY regular session is available and
are used for stratified reporting, never for same-day entry decisions:

- `trend_up`: SPY 16:00 close is at least 0.75% above its 09:30 open;
- `trend_down`: SPY 16:00 close is at least 0.75% below its 09:30 open;
- `range`: absolute open-to-close return is below 0.75%;
- append `_high_vol` when `(session_high - session_low) / session_open >=
  1.50%`, otherwise append `_normal_vol`.

The collection must include at least 15 sessions in each of the three
directional regimes (`trend_up`, `trend_down`, and `range`). Volatility suffixes
are descriptive until each suffix has at least 15 sessions.

The frozen universe must contain at least 20 symbols across at least 5
recognized sectors. Sector labels must be frozen from locally stored metadata
before outcome analysis. SPY and QQQ are classified as `broad_market_etf`, not
as a corporate sector, and cannot by themselves satisfy sector diversity.
Unknown sector labels are reported and excluded from sector-specific claims.

### Session rejection rules

Reject a symbol-session from strategy testing when any of these applies:

1. Recording starts after 04:00 for extended-session validation or after 09:30
   for strategy eligibility.
2. Any required 09:30 opening minute or later causal input is absent,
   incomplete, duplicated without one accepted canonical event, or received
   too early to be closed.
3. An unexplained event-sequence gap, recorder gap, corrupt checksum, truncated
   recording, failed recovery, or discontinuity overlaps a required window.
4. A reconnect occurs without explicit continuity proof or backfill covering
   the disconnected interval.
5. A valid quote is stale for more than 30 continuous seconds before a decision
   or is unavailable/stale at an order event.
6. Session boundaries, holiday status, early-close status, timezone, or DST
   conversion cannot be verified from the recorded market-clock/session state.
7. Required OHLCV or provider VWAP input is missing, nonfinite, nonpositive
   where positivity is required, or internally inconsistent.
8. A halt or price-basis-changing corporate action is unresolved.
9. Source or coverage mode changes within the symbol-session.
10. The recording ends before an open order or position has a causally
    supported exit; that trade is censored and excluded from performance
    metrics even if earlier signals remain auditable.

Every rejection must have a stable reason code. Never repair a rejected session
with external or later-acquired data.

### Exact backtest eligibility criteria

A backtest run is eligible for mechanics validation only if:

- recording checksum and completion status pass;
- replay produces identical state across three runs;
- the symbol universe and feed stratum were frozen before outcomes;
- all session and symbol-session rejection checks have run;
- causal indicator and decision ledgers are complete;
- no order uses an event before its receipt or latency eligibility time;
- all ambiguous intrabar outcomes are excluded from the primary result.

A backtest run is eligible for a performance claim only if it also meets the
strategy-specific session, symbol, sector, regime, signal, and completed-trade
thresholds; uses a chronological 60/20/20 date split; freezes code and
parameters before holdout access; and reports every rejection, censoring, and
execution sensitivity. Failure of any condition restricts the output to data
quality and mechanics observations.

### Exact replay validation checks

For every accepted recording:

1. Verify the compressed-file checksum before loading events.
2. Replay three times and require identical event-order, state, bar, quote,
   signal, order, fill, position, and result digests.
3. Require monotonic `(receipt_timestamp, index)` processing and prove no
   decision uses an event with a later receipt timestamp.
4. Verify that each one-minute bar becomes available only after its close and
   recorded receipt; verify the same for every derived 5-, 15-, and 30-minute
   range.
5. Recalculate session VWAP, EMA9, ATR14, OR5, OR15, and OR30 independently
   from the recorded inputs and require exact deterministic agreement within a
   declared floating-point tolerance of `1e-9`.
6. Compare provider one-minute OHLCV/VWAP with the replay state and list every
   mismatch, duplicate, incomplete minute, and condition-based explanation.
7. Verify reconnect intervals, sequence gaps, stale periods, and recovery
   markers against the eligibility decision.
8. Verify each simulated order's submission time, latency eligibility,
   non-stale quote, bid/ask reference, trade-through evidence, partial fills,
   slippage, stop/target ordering, cancellation, and 15:55 flatten attempt.
9. Assert that no live or Alpaca paper order route is invoked and no replay
   state reaches production storage.
10. Produce a machine-readable manifest containing input checksum, document
    version/commit, parameters, exclusions, digests, and verdict.

### Staged experiment plan

#### Stage A — Data sufficiency

Inventory completed local recordings and apply all rejection rules without
calculating returns. Report eligible dates, symbol-sessions, sectors, regimes,
signals possible, gaps, stale periods, reconnect continuity, and missing
fields. Exit criterion: all minimum session/symbol/sector/regime coverage and
required field checks pass. The current corpus fails here.

#### Stage B — Mechanics validation

Implement research-only calculations against replay after a separate explicit
authorization. Use hand-constructed deterministic fixtures plus eligible
recordings to verify causal indicator updates, exact signals, order timing,
partial exits, stops, targets, ambiguity policy, censoring, and three-run
digests. Exit criterion: all exact replay checks pass with no unexplained
differences. Do not report strategy performance.

#### Stage C — Baseline backtest

Freeze `orb_v1` and `vwap_pullback_v1`, then run the earliest 60% development
and next 20% validation dates. Report the full metric and exclusion set already
specified, separated by strategy, side, feed, regime, sector, and gap class
where sample thresholds permit. Do not choose a winner or alter parameters.

#### Stage D — Out-of-sample test

Lock code, document hash, data manifest, and execution assumptions before
revealing the final 20% of dates. Run once, preserve null results, and label
every post-lock rerun or correction. No edge claim is permitted unless the
overall and side-specific completed-trade thresholds remain satisfied in the
holdout reporting scope.

#### Stage E — Forward paper validation

Only after Stages A–D pass and a separate safety review authorizes it, observe
signals prospectively in a paper-only environment for at least 20 additional
complete regular sessions and 30 completed paper trades per strategy. Freeze
parameters, prohibit live-money routing, reconcile every signal/order/fill
against replay, and report deviations. This stage validates operational
behavior, not profitability.

### Data acceptance verdict

- **Current recordings usable for ORB or VWAP Pullback testing:** **No.**
- **Specific new recordings required:** continuous, completed, checksum-valid
  local recordings from 04:00 through 20:00 New York, with gap-free regular
  one-minute OHLCV/provider-VWAP data, causally ordered quotes and trades,
  explicit continuity/recovery evidence, at least 60 eligible sessions, at
  least 20 frozen symbols, at least 5 sectors, and the regime/sample coverage
  defined above.
- **Before either strategy can be coded or tested:** Stage A must pass; the
  source/coverage stratum and universe must be frozen; session rejection and
  replay checks must be executable; all indicator inputs must be present from
  09:30; and any research implementation must receive separate authorization.
- **Before any performance claim:** the applicable signal/trade thresholds,
  chronological split, locked holdout, deterministic replay, execution audit,
  and Stage D requirements must all pass. No current result supports an edge,
  a performance estimate, or a preferred strategy.
