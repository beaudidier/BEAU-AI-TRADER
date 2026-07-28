# Day Trading Foundation — Independent Audit

**PR:** #2, `feature/day-trading-foundation`

**Audited head:** `fe18392` (`feat: intraday recorder and deterministic replay`)

**Comparison base:** `main`

**Audit date:** 2026-07-28

**Scope:** WebSocket reliability, data loss, recorder recovery, replay determinism, bar aggregation, session/timezone handling, paper execution realism, risk controls, race conditions, secret handling, and IEX coverage.

## Executive verdict

**Do not merge for production or decision-grade research in the current form.**

The foundation has useful safeguards: TLS certificate verification is enabled, secrets are server-side, raw recording uses an allowlist, live-money routing is not connected to the HTTP order endpoints, quotes and bars reject obvious invalid/future data, and tests cover many nominal and synthetic failure cases. However, the implementation cannot yet guarantee loss-aware capture, crash-safe recovery, provenance-safe replay, or durable risk enforcement. Several shared runtime objects are also mutated without a consistent concurrency boundary.

No finding is classified Critical because the exposed order path is an in-memory paper simulator and the Alpaca paper client is not wired to it. Six High findings are release blockers for a reliable day-trading research foundation.

| Severity | Count |
|---|---:|
| Critical | 0 |
| High | 6 |
| Medium | 7 |
| Low | 3 |

## Critical

No Critical findings.

## High

### H-01 — Reconnects can silently leave permanent market-data holes

**Areas:** WebSocket reliability, data loss

**Evidence:** `backend/day_trading/stream_manager.py:125-174,176-229,275-280`; `backend/day_trading/health.py:183-199`

The reconnect loop reauthenticates and resubscribes, but it does not identify the disconnect interval, request a REST backfill, reconcile sequence numbers, or prevent consumers from treating the stream as complete. Events older than the last accepted timestamp are deliberately discarded from live consumers after reconnect. REST bar history is loaded only once per ticker by `ensure_bars`; it is not a reconnect repair mechanism.

**Impact:** A transient disconnect or delayed provider delivery can permanently omit trades, quotes, and bars from the live cache and aggregation. The raw recorder may describe some rejected late events, but events never delivered during the outage are unrecoverable, and downstream bars can continue after a gap.

**Required remediation:** Track a high-water mark per symbol/event type, mark the interval incomplete at disconnect, backfill authoritative bars after reconnect, reconcile sequence/timestamps, and expose a degraded state until reconciliation completes. Never silently discard a late bar needed to close a known gap.

### H-02 — Recorder “recovery” does not recover the principal crash-corruption case

**Areas:** Recorder recovery, data loss

**Evidence:** `backend/day_trading/recorder.py:156-249,290-320`

Recovery first reads the entire existing gzip stream and then appends a new gzip member. If the process or host dies while the current gzip member is being written, the member may lack a valid trailer; `gzip.open(..., "rt")` can then raise before `start` opens the append writer. There is no scan-to-last-valid-record, truncation to a verified boundary, quarantine, sidecar journal, or recovery error state. The `recovered` flag therefore proves only that a file existed, not that it was repaired.

The recorder also persists metadata only every 1,000 events (plus clean stop), and it does not rebuild `_last_provider_timestamp` or `_last_sequence` while reading existing records. After a successful resume, cross-crash duplicates, ordering regressions, sequence gaps, and bar gaps are not detected against the pre-crash tail.

**Impact:** The failure mode recovery is intended to handle can make a session non-resumable. Even when resume succeeds, continuity diagnostics across the restart boundary are incomplete.

**Required remediation:** Use independently checksummed chunks or uncompressed append-only records with atomic rotation; scan and truncate/quarantine only the invalid tail; rebuild all continuity state from the recovered tail; persist a durable checkpoint frequently; and test forced termination during a write.

### H-03 — Replay accepts altered recordings without enforcing the recorded checksum

**Areas:** Replay determinism, data integrity

**Evidence:** `backend/day_trading/replay.py:275-289,575-603`; `backend/day_trading/recorder.py:515-538`

`_load` requires metadata status `completed` but never compares the data file to `checksum_sha256`. Checksum verification is a separate API result and does not gate replay, bar verification, or determinism verification. A syntactically valid recording can be edited and replayed successfully while its metadata checksum is invalid.

`verify_determinism` then runs the same already-sorted in-memory event list through the same implementation three times. Matching digests demonstrate repeatability of that process, not authenticity of the input, correct ordering semantics, isolation from concurrent controls, or equivalence to the original live state.

**Impact:** Tampered, partially replaced, or incorrectly recovered data can produce a “deterministic” result and be used as research evidence.

**Required remediation:** Make checksum and event-count validation mandatory before every replay/verification operation; bind metadata and data in one signed or content-addressed manifest; reject duplicate/non-contiguous indexes; and compare replay output to independently captured expected checkpoints.

### H-04 — Immediate stop entries can bypass cash and per-trade risk admission

**Areas:** Risk controls, paper execution realism

**Evidence:** `backend/day_trading/paper_broker.py:101-152,154-166,217-239,259-274`

For a stop order, entry admission calculates risk and required cash using `stop_price`. If the stop is already triggered, `_should_fill` immediately fills at the current ask. `_fill` does not rerun admission using that actual fill. When the ask is above the stop trigger, the fill can consume more cash and create more stop distance than the values admitted by `_validate_entry`.

**Impact:** A gapping or already-triggered stop order can create negative cash or exceed the stated 0.25% maximum risk per trade despite receiving an accepted status.

**Required remediation:** Perform the final atomic admission check using the actual modeled fill price immediately before every fill, including immediate fills; reserve cash/risk for pending orders; reject or resize when the actual fill violates limits; and add gap-through-stop regression tests.

### H-05 — Paper risk state and the emergency switch are process-local and reset on restart

**Areas:** Risk controls, recorder/recovery interaction

**Evidence:** `backend/day_trading/paper_broker.py:31-58`; `backend/day_trading/health.py:26-53`

Cash, positions, closed trades, idempotency keys, the daily-loss baseline/lock, pending orders, and the emergency switch all exist only in memory. A deployment, crash, worker recycle, or second API worker creates a fresh $100,000 account and loses the prior loss lock and open-position state.

**Impact:** Daily loss and maximum-open-trade limits are not durable and are not global across workers. The same idempotency key can execute once per process. Restarting can erase positions that should be flattened and reset a breached daily-loss lock.

**Required remediation:** Store account/order/position/risk state transactionally in a durable database, scope it to an authenticated account, enforce constraints in the transaction that creates/fills an order, and restore/flatten safely on startup.

### H-06 — Replay and control endpoints race on shared mutable state

**Areas:** Race conditions, replay determinism

**Evidence:** `backend/day_trading/replay.py:256-343,357-424,426-486,510-573`; `backend/day_trading/router.py:207-313`

The replay worker modifies `cursor`, state, digests, quotes, bars, orders, and fills while status, pause/resume, seek/reset, order submit, and cancel access the same objects from request threads. The engine lock is used around `start` and `seek`, but not by `_run`, `_process`, status, execution submission, or cancellation. `ReplayExecutionSimulator.on_event` iterates `self.orders.values()` while an HTTP request can insert an order, which can raise “dictionary changed size during iteration” and terminate the replay.

`seek` and `reset` join the worker for only two seconds and then replace shared structures even if the worker remains alive.

**Impact:** User timing can change replay output, lose controls, corrupt snapshots, or put the engine into an error state. This directly contradicts the determinism claim.

**Required remediation:** Serialize all replay commands and event processing on one owner thread/event loop, or enforce one lock around every shared-state access. Require confirmed worker termination before reset, and include concurrent control/order tests.

## Medium

### M-01 — Authentication/subscription errors do not fail the WebSocket connection

**Areas:** WebSocket reliability

**Evidence:** `backend/day_trading/stream_manager.py:176-209,252-262`

The manager marks itself `CONNECTED` immediately after sending auth and subscription messages, before it receives success acknowledgements. Provider `error` frames only increment `invalid_events`; they do not close/reconnect or move the stream to `ERROR`. Any inbound control/error traffic also refreshes `last_heartbeat_at`.

**Impact:** Bad credentials, a rejected subscription, or an entitlement error can be reported as a connected/non-stale stream until the receive timeout, and repeated control traffic can mask the absence of market data.

**Required remediation:** Implement an explicit authentication/subscription handshake with deadlines, validate the acknowledged symbol sets, treat fatal provider errors as connection failures, and track control heartbeat separately from last market-data event.

### M-02 — Day-trading mutation endpoints are unauthenticated and share one global account

**Areas:** Secret handling, risk controls, race conditions

**Evidence:** `backend/day_trading/router.py:14-21,101-192,207-313`; compare authenticated dependencies in `backend/saas/router.py`

The router does not depend on `get_current_user`. Any client that can reach the API can enable/disable paper orders, submit/cancel orders, flatten state indirectly, start/stop recordings, control replay, and inspect recorded session metadata when research mode is enabled. The frontend client also sends no bearer token for these calls.

**Impact:** In a shared staging deployment, users interfere with the same singleton runtime and can corrupt each other’s research state. This is not a live-money exposure today because the external Alpaca paper adapter is not wired to the route.

**Required remediation:** Require authentication and an explicit research/admin entitlement for all day-trading endpoints; partition state by user/workspace; and use CSRF-safe authenticated mutations where applicable.

### M-03 — Bar completeness can mislabel missing-minute buckets

**Areas:** Bar aggregation

**Evidence:** `backend/day_trading/bar_aggregator.py:91-160`

A 5m/15m bucket is `GAP` only when two present items are non-contiguous. A bucket containing a single minute, or a contiguous subset missing minutes at its beginning/end, becomes `INCOMPLETE` even after the bucket has ended. Completeness is stored on ingestion and never advances based on clock time. Duplicate timestamp bars are dropped, so provider corrections cannot replace a provisional bar.

**Impact:** Historical holes can look like merely open/in-progress bars, and corrected official values can be ignored. Strategies may consume partial OHLCV without a definitive data-loss marker.

**Required remediation:** Evaluate completeness against bucket end time and the exact expected session-minute set; distinguish `OPEN`, `PARTIAL`, and `GAP`; support versioned provider corrections; and exclude cross-session minutes explicitly.

### M-04 — Session calendar is a handcrafted approximation

**Areas:** Session and timezone handling

**Evidence:** `backend/day_trading/session.py:60-128`

Timezone conversion correctly uses `America/New_York`, including DST. However, trading days and early closes are generated from a small fixed rule set rather than an exchange calendar. The model cannot represent ad-hoc closures, exceptional schedules, rule changes, or provider-specific session calendars. Naive datetimes are silently interpreted as UTC by `as_utc`, which can shift caller-supplied local times.

**Impact:** Orders, flattening, replay admission, and UI transitions can be wrong on exceptional exchange days or when a caller sends a naive Eastern timestamp.

**Required remediation:** Use an authoritative NYSE calendar (or Alpaca clock/calendar endpoint), cache dated sessions, fail closed if the calendar is unavailable/out of range, and reject naive external datetimes.

### M-05 — Live paper fills are materially more optimistic than market execution

**Areas:** Paper execution realism

**Evidence:** `backend/day_trading/paper_broker.py:237-286,288-336,367-393`

Market orders fill instantly for the entire quantity at the top-of-book ask/bid. Quote size is ignored; there is no latency, queue position, slippage, partial fill, halt, auction, trade-through, or price-band model. Pending limits trigger from quotes alone and fill fully. Protective stops trigger from bid and fill exactly at bid. End-of-day flattening can use the last midpoint when no quote exists, regardless of staleness.

**Impact:** Fill rates, costs, drawdowns, and risk-limit behavior are systematically optimistic, especially on IEX-only data or illiquid symbols.

**Required remediation:** Label this explicitly as a simplified simulator; model latency, quote size/depth, partial fills, slippage, stale/no-market rejection, and gap-through stops; use trade prints to establish limit execution eligibility; and report sensitivity ranges.

### M-06 — Replay execution violates limit-price semantics and over-allocates prints

**Areas:** Paper execution realism, replay determinism

**Evidence:** `backend/day_trading/replay.py:189-253`

The replay simulator applies adverse slippage after clamping the reference to the limit, so a buy limit can fill above its limit and a sell limit below its limit. Each pending order independently receives up to the full size of the same trade event; aggregate simulated fills can exceed recorded print liquidity. Quotes use receipt time in the execution cache, while the visible replay quote uses provider time, creating inconsistent staleness semantics.

**Impact:** Replay produces impossible fills and can overstate executable capacity.

**Required remediation:** Never cross the limit after fees/slippage rules; allocate each print’s remaining liquidity once in deterministic price-time order; define one event-time policy; and test multiple competing orders.

### M-07 — IEX limitations are labeled but not enforced in decision/risk semantics

**Areas:** IEX coverage limitations

**Evidence:** `backend/providers/alpaca_market_provider.py:42-47,94-149`; `backend/day_trading/stream_manager.py:315-319`; `backend/day_trading/paper_broker.py:128-152`

The API labels IEX as `partial-market`, which is good. Nevertheless, IEX quotes, trades, volume, VWAP, bars, spreads, stops, and fills are consumed identically to SIP data. IEX represents a single venue, not the consolidated US market; observed volume and prices can differ from NBBO/consolidated prints, and quiet IEX intervals are not proof that the market was quiet.

**Impact:** Spread filters, liquidity assumptions, stop triggers, bar reconstruction, gap detection, and execution results may not generalize to consolidated-market trading.

**Required remediation:** Block decision-grade execution/risk claims on partial coverage; make feed coverage part of every derived artifact and experiment manifest; calibrate only against the same feed; warn on symbols with poor IEX participation; and require SIP or another consolidated source before production validation.

## Low

### L-01 — Reconnect backoff has no jitter and attempt state never resets

**Areas:** WebSocket reliability

**Evidence:** `backend/day_trading/stream_manager.py:125-174`

Backoff is deterministic (`1, 2, 4, ... 30`) with no jitter. Because one connection attempt lasts until disconnection, the attempt counter/backoff does not reset after a long healthy connection.

**Impact:** Multiple workers can reconnect in lockstep, and a later unrelated outage starts at the maximum delay.

**Required remediation:** Reset failure count after a stable connection and use bounded full jitter.

### L-02 — Recorder durability is batched and not guaranteed by `flush`

**Areas:** Recorder recovery, data loss

**Evidence:** `backend/day_trading/recorder.py:290-320`

Every event flushes Python/gzip buffers, but storage is synced only each 1,000 events. A host/power failure can lose an OS-buffered tail even though the in-memory count advanced.

**Impact:** The recording tail and metadata can diverge after a hard failure.

**Required remediation:** Define an explicit durability target, fsync at a time/size cadence consistent with it, and expose the last durable index.

### L-03 — Secret controls are useful but incomplete as a security boundary

**Areas:** Secret handling

**Evidence:** `backend/day_trading/recorder.py:25-57,80-90,290-295,322-415`; `.gitignore`; `backend/.env.example`

Positive controls include a raw-field allowlist, recursive secret-key-name rejection, ignored recording storage, server-side environment variables, TLS verification, and error messages that omit response bodies. The marker check is key-name based rather than value/DLP based, and credentials remain long-lived strings on singleton objects for the process lifetime. File permissions and encryption-at-rest for recordings are not set explicitly.

**Impact:** A future newly allowed field containing a credential-like value could evade the detector, while harmless keys containing a marker can stop recording. Local recording confidentiality depends on host defaults.

**Required remediation:** Keep the allowlist minimal, add value-pattern/redaction tests, use least-privilege data-only credentials, rotate credentials, and create recording directories/files with explicit restrictive permissions.

## Cross-cutting acceptance criteria before merge

1. Demonstrate forced WebSocket disconnect/reconnect with a missing interval that is detected, backfilled, reconciled, and marked complete only after verification.
2. Demonstrate recorder recovery from termination during a physical write, including a corrupted/truncated tail, with continuity state restored.
3. Make checksum validation a mandatory replay precondition and prove altered input is rejected.
4. Serialize replay commands and event processing; pass concurrent submit/cancel/seek/reset stress tests.
5. Revalidate cash, exposure, and stop risk atomically at actual fill price; persist all risk state and idempotency across restart/workers.
6. Replace the handcrafted market calendar with authoritative dated sessions and test DST, early closes, and exceptional closures.
7. Correct gap/completeness semantics and limit-order execution semantics.
8. Authenticate and authorize all mutating endpoints, partition state, and explicitly restrict IEX artifacts to partial-coverage research.

## Validation performed

- Reviewed all 34 files in the `main...feature/day-trading-foundation` diff, with detailed tracing of the stream, recorder, replay, aggregator, session/clock, quote cache, paper broker, providers, API router, frontend API client, and related tests.
- Ran the seven focused day-trading test modules with Python `unittest`: **53 tests passed**.
- `pytest` was not available in the environment; the same test modules are `unittest`-compatible and completed successfully.
- No application code was modified.
