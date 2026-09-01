# Day Trading Foundation — Post-Milestone-58 Delta-Audit Plan

## Purpose and boundaries

This document prepares a future, evidence-based delta audit. It does not perform that audit and does not change the status of any finding in `DAY_TRADING_FOUNDATION_AUDIT.md`.

- Audit baseline commit: `20bbc998adb79659020c5ca516645461f36ab788`
- Originally audited foundation: `fe18392`
- Future target: `<future final Milestone 58 commit>`
- Scope: documentation and audit procedure only
- Default status of every finding below: `OPEN` until the target commit supplies all required evidence
- Forbidden inference: a code change, passing unit test, or Milestone 58 completion alone never proves a finding resolved

Status rules:

- `RESOLVED`: every required code, regression, and runtime/live-evidence condition is satisfied, with no contradictory evidence.
- `PARTIALLY RESOLVED`: a material part of the failure mode is fixed and tested, but one or more required conditions remain absent or unproven.
- `OPEN`: the vulnerable path remains, the evidence is missing, the test does not exercise the stated failure mode, or observed behavior contradicts the acceptance condition.

## High-finding matrix

### H-01 — Reconnect gap repair

- Likely modules: `backend/day_trading/stream_manager.py`, `backend/day_trading/health.py`, `backend/day_trading/bar_aggregator.py`, provider REST-history code, and `backend/tests/test_day_trading_stream.py`.
- `RESOLVED` evidence: disconnect boundaries and per-symbol/event high-water marks are recorded; reconnect initiates authoritative REST backfill for the exact missing interval; live and backfilled events are deterministically deduplicated/reconciled; incomplete/degraded state remains visible until repair verifies no unrepaired gaps; late events needed for known gaps are retained; replay of the repaired capture is deterministic; the forced-disconnect runtime trace shows zero silent event loss.
- `PARTIALLY RESOLVED` evidence: gaps are detected or backfilled, but coverage, deduplication, degraded-state semantics, late-event reconciliation, or deterministic replay is incomplete or proven only synthetically.
- `OPEN` evidence: reconnect only resubscribes; gaps are inferred but not repaired; old events are discarded; success is claimed from connectivity alone; or any event range disappears without a durable gap record.
- Regression tests: forced disconnect with controlled missing boundaries; overlapping REST/live events; duplicate and late delivery; multi-symbol/event-type gaps; failed/partial backfill; no premature healthy state; repaired-recording replay digest stability.
- Runtime/live evidence: timestamped provider disconnect/reconnect trace, requested and received REST ranges, reconciliation counts, durable gap-state transitions, and source-to-record index accounting proving zero silent loss.
- Milestone 58 fit: realistic only if it implements and demonstrates end-to-end reconnect repair. Mismatch explanation alone cannot resolve H-01.

### H-02 — Recorder recovery

- Likely modules: `backend/day_trading/recorder.py`, `backend/day_trading/models.py`, and `backend/tests/test_day_trading_recorder_replay.py`.
- `RESOLVED` evidence: a physically truncated/corrupt gzip tail is detected; only the invalid tail is truncated or quarantined; restart/resume succeeds; provider timestamp, sequence, index, gap, and durability state are rebuilt from verified records/checkpoints; the resumed stream contains no duplicated or skipped event range.
- `PARTIALLY RESOLVED` evidence: corruption is rejected or quarantined safely, but resumability, continuity restoration, durable checkpointing, or cross-restart duplicate/gap detection remains incomplete.
- `OPEN` evidence: recovery merely detects an existing file; full gzip read still fails on a missing trailer; continuity state resets; or only clean-stop recovery is tested.
- Regression tests: kill during physical write at multiple offsets; truncated trailer/member; corrupt tail bytes; clean multi-member resume; restored high-water/sequence state; duplicate and missing boundary events; crash between data and metadata persistence.
- Runtime/live evidence: forced process termination, pre/post file hashes and valid boundary, recovery report, restored checkpoint values, continuous event-index/sequence ledger, and successful deterministic replay of the recovered session.
- Milestone 58 fit: possible if recorder repair and continuity restoration are in scope; otherwise a later durability milestone is required.

### H-03 — Mandatory checksum validation

- Likely modules: `backend/day_trading/replay.py`, `backend/day_trading/recorder.py`, `backend/day_trading/router.py`, and `backend/tests/test_day_trading_recorder_replay.py`.
- `RESOLVED` evidence: every replay, bar verification, and determinism entry point validates the data/metadata binding, checksum, event count, and contiguous unique indexes before state creation; invalid input is refused; corrupted data cannot enter replay state; verification emits an immutable/content-addressed report.
- `PARTIALLY RESOLVED` evidence: checksum validation gates some paths but not all, or invalid input is detected after replay state is created, or the report is mutable/unbound.
- `OPEN` evidence: verification remains optional; a syntactically valid altered recording replays; metadata and data can be substituted independently; or duplicate/non-contiguous indexes are accepted.
- Regression tests: single-byte edit, truncation, metadata substitution, wrong event count, duplicate/missing indexes, checksum absence, and calls through every replay/verification API.
- Runtime/live evidence: preserved invalid sample and immutable verification artifact showing pre-state rejection, plus a valid session proving normal replay remains deterministic.
- Milestone 58 fit: realistically addressable if integrity-gating changes are included; mismatch analysis without mandatory gates does not resolve it.

### H-04 — Immediate stop-order risk bypass

- Likely modules: `backend/day_trading/paper_broker.py`, `backend/day_trading/models.py`, `backend/day_trading/router.py`, and `backend/tests/test_day_trading_paper_broker.py`.
- `RESOLVED` evidence: every stop activation performs cash/exposure/per-trade-risk checks using the modeled actual fill price immediately before fill; admission and state mutation are atomic; pending orders reserve risk/cash; immediate and gap-through triggers cannot bypass checks and are rejected or resized when limits fail.
- `PARTIALLY RESOLVED` evidence: immediate stops are rechecked but admission is non-atomic, reservations are absent, concurrent fills can overcommit, or some trigger path bypasses final validation.
- `OPEN` evidence: validation uses only submitted stop price; `_fill` can execute without final risk admission; or accepted fills can produce negative cash/excess risk.
- Regression tests: already-triggered buy/sell stops, large gap through stop, insufficient cash at fill, risk-distance expansion, pending-order reservation contention, and concurrent activations at the risk boundary.
- Runtime/live evidence: order ledger showing submitted trigger, modeled fill, final atomic risk calculation, reservation/transaction outcome, and invariant checks after each activation.
- Milestone 58 fit: likely later unless Milestone 58 explicitly changes paper-order admission; bar mismatch explanation alone cannot resolve it.

### H-05 — Persistent risk, idempotency, and emergency state

- Likely modules: `backend/day_trading/paper_broker.py`, `backend/day_trading/health.py`, `backend/day_trading/router.py`, application startup/storage wiring, and `backend/tests/test_day_trading_api.py` plus `backend/tests/test_day_trading_paper_broker.py`.
- `RESOLVED` evidence: cash, positions, orders, fills, closed trades, pending reservations, idempotency keys, loss baseline/lock, and emergency-disable state persist transactionally; restart restores them; multiple workers share one authoritative state; duplicate order admission is impossible; emergency disable survives restart.
- `PARTIALLY RESOLVED` evidence: some state persists but a risk-critical or idempotency field is process-local, restoration is incomplete, or multi-worker atomicity is unproven.
- `OPEN` evidence: singleton/in-memory reset remains; the same idempotency key executes per worker; restart clears a loss lock, emergency state, or positions.
- Regression tests: restart with positions/pending orders/loss lock/emergency disable; simultaneous duplicate keys across workers; concurrent risk admissions; transactional failure/rollback; safe startup restoration.
- Runtime/live evidence: two-worker test against shared storage, process restart trace, durable before/after state snapshots, duplicate-attempt ledger, and persisted emergency-disable proof.
- Milestone 58 fit: requires a dedicated durable-state milestone unless explicitly included; not realistically resolved by mismatch analysis.

### H-06 — Shared-state races

- Likely modules: `backend/day_trading/replay.py`, `backend/day_trading/router.py`, replay execution/control models, and `backend/tests/test_day_trading_recorder_replay.py` plus `backend/tests/test_day_trading_api.py`.
- `RESOLVED` evidence: replay event processing and all controls/mutations have one serialization owner or a complete synchronization boundary; status snapshots are consistent; submit/cancel/pause/resume/seek/reset are ordered deterministically; reset requires confirmed worker termination; state handling is thread- and process-safe where shared across processes.
- `PARTIALLY RESOLVED` evidence: individual dictionary races are fixed but command ordering, snapshot consistency, termination, or multi-process semantics remain unproven.
- `OPEN` evidence: worker and HTTP threads mutate the same objects independently; iteration can race with insertion/removal; timed join permits old and replacement state to coexist; user timing changes results.
- Regression tests: concurrent submit/cancel while iterating; repeated pause/resume/seek/reset storms; termination timeout; deterministic command ordering; status reads during mutation; multi-worker controls if the API supports them.
- Runtime/live evidence: sustained concurrency/stress run with command/event trace, zero race exceptions, confirmed worker lifecycle, invariant checks, and identical outcome digests across repeated schedules.
- Milestone 58 fit: later unless it explicitly serializes replay/control state. Mismatch explanation alone cannot resolve H-06.

## Medium-finding matrix potentially affected by Milestone 58

### M-02 — Unauthenticated global day-trading mutations

- Likely modules: `backend/day_trading/router.py`, authentication dependencies in `backend/saas/router.py`, frontend day-trading API client, and `backend/tests/test_day_trading_api.py`.
- `RESOLVED`: every mutation and sensitive read requires authenticated, entitled access; state is partitioned by user/workspace; cross-tenant access is denied; mutation protections match the authentication architecture.
- `PARTIALLY RESOLVED`: authentication exists but authorization, partitioning, or every route is incomplete.
- `OPEN`: anonymous/global mutations remain or singleton state is shared among users.
- Regression tests: unauthenticated/unauthorized denial, entitlement matrix, cross-user isolation, and authenticated happy paths.
- Runtime/live evidence: staging request audit showing identity, authorization result, tenant key, and no cross-tenant state visibility.
- Milestone 58 fit: later security/state milestone; not a bar-mismatch explanation deliverable.

### M-03 — Incomplete bar-gap semantics

- Likely modules: `backend/day_trading/bar_aggregator.py`, `backend/day_trading/session.py`, `backend/day_trading/models.py`, and `backend/tests/test_day_trading_data_integrity.py`.
- `RESOLVED`: completeness uses the exact expected session-minute set and current/bucket-end time; `OPEN`, `PARTIAL`, and `GAP` are distinct; missing leading/trailing/single-minute buckets become gaps after close; provider corrections are versioned/reconciled; cross-session minutes are excluded.
- `PARTIALLY RESOLVED`: interior gaps are fixed but boundary, clock-transition, session, or correction semantics remain incomplete.
- `OPEN`: contiguous subsets or single-minute closed buckets remain `INCOMPLETE`, or completeness never advances with time.
- Regression tests: missing first/last/interior minutes, one-minute bucket, clock crossing bucket end, early close/session edge, duplicate correction, and repaired gap transitions.
- Runtime/live evidence: expected-versus-observed minute ledger for representative sessions and the 124 mismatch corpus, including classification transitions and correction provenance.
- Milestone 58 fit: directly relevant if mismatch root causes include gap/completeness semantics; explanation alone is not remediation.

### M-04 — Exchange-calendar handling

- Likely modules: `backend/day_trading/session.py`, `backend/day_trading/market_clock.py`, provider calendar integration, and `backend/tests/test_day_trading_session.py`.
- `RESOLVED`: authoritative dated exchange sessions drive admission and aggregation; DST, standard/exceptional early closes, ad-hoc closures, and out-of-range/calendar-unavailable behavior fail safely; naive external datetimes are rejected.
- `PARTIALLY RESOLVED`: authoritative calendar covers normal/early-close days but exceptional/unavailable/naive-time handling is incomplete.
- `OPEN`: handcrafted holiday rules remain authoritative or unsupported dates silently use approximations.
- Regression tests: DST boundaries, standard and exceptional early closes, ad-hoc closure, unavailable/out-of-range calendar, and naive timestamp rejection.
- Runtime/live evidence: cached/provider calendar provenance and comparison of session boundaries for mismatch dates.
- Milestone 58 fit: possible if mismatch attribution identifies calendar boundaries and implements authoritative handling; otherwise later milestone.

### M-05 — Optimistic paper fills

- Likely modules: `backend/day_trading/paper_broker.py`, `backend/day_trading/quote_cache.py`, models/reporting, and `backend/tests/test_day_trading_paper_broker.py`.
- `RESOLVED`: simulator is explicitly labeled; fill logic models latency, available size/depth, partial fills, slippage, stale/no-market rejection and gap-through stops; limit eligibility uses appropriate prints; results disclose assumptions/sensitivity.
- `PARTIALLY RESOLVED`: labeling or selected realism controls exist but material full-fill/top-of-book optimism remains.
- `OPEN`: full quantity still fills instantly at top of book regardless of liquidity/latency/staleness.
- Regression tests: insufficient quote size, partial fills, latency price change, stale/no quote, illiquid spread, halt/no market, gap-through stop, and trade-print limit eligibility.
- Runtime/live evidence: paper-versus-observed market comparison with fill-rate, slippage, capacity, and sensitivity distributions.
- Milestone 58 fit: later execution-simulation milestone; mismatch work may inform inputs but cannot resolve fill realism alone.

### M-07 — IEX partial-market limitations

- Likely modules: `backend/providers/alpaca_market_provider.py`, `backend/day_trading/stream_manager.py`, `backend/day_trading/paper_broker.py`, derived-artifact metadata/reporting, and provider/day-trading tests.
- `RESOLVED`: feed coverage is propagated into every derived artifact/manifest; partial-market data is blocked from decision-grade execution/risk claims; poor-participation warnings and same-feed calibration are enforced; production validation requires consolidated coverage.
- `PARTIALLY RESOLVED`: labels/warnings propagate but enforcement or calibration constraints remain incomplete.
- `OPEN`: IEX data remains behaviorally interchangeable with consolidated data despite a display label.
- Regression tests: coverage provenance propagation, restricted decision-grade modes, poor-participation warning, same-feed calibration validation, and consolidated-feed acceptance.
- Runtime/live evidence: representative IEX-versus-consolidated comparison for prices, volume, spread, quiet intervals, gaps, and the mismatch corpus, with manifest provenance.
- Milestone 58 fit: mismatch explanation may quantify the limitation; policy/enforcement likely belongs to a later milestone.

## Delta-audit execution procedure

Do not execute this procedure until Chat 1 supplies the final Milestone 58 commit.

1. Record immutable inputs: base `fe18392`, audit baseline `20bbc998adb79659020c5ca516645461f36ab788`, target `<future final Milestone 58 commit>`, repository cleanliness, and complete commit ancestry.
2. Review only the target delta and its directly affected call paths. Map every changed file and test to the findings above; do not infer closure from commit messages.
3. Reproduce the original failure mode for each affected finding before evaluating the remediation. Preserve commands, fixtures, logs, hashes, timestamps, and environment details.
4. Evaluate every finding independently as `RESOLVED`, `PARTIALLY RESOLVED`, or `OPEN` using the criteria above. Missing runtime/live proof caps the status at `PARTIALLY RESOLVED` when that proof is required.
5. Run the specified regression tests plus all existing focused day-trading tests. Record exact pass/fail/skip counts and investigate changed expectations rather than accepting snapshot updates automatically.
6. Inspect runtime/live artifacts for provenance, completeness, reproducibility, and contradictions. Keep the 124 live-bar mismatches visible until each is explained or repaired with evidence.
7. Search the delta and affected paths for new Critical/High findings, regressions, cross-finding interactions, and weakened safeguards.
8. Produce a finding-by-finding status table containing evidence links/hashes, new Critical/High findings, regressions, remaining merge blockers, and unresolved evidence gaps.
9. Issue exactly one final recommendation:
   - `ACCEPT FOR RESEARCH`: no Critical/High blockers remain for the stated research scope and all required evidence is present.
   - `REJECT FOR RESEARCH`: one or more Critical/High blockers or material regressions remain.
   - `NOT READY TO ASSESS`: the target or required evidence is absent, incomplete, unverifiable, or non-reproducible.

The delta audit must not authorize production, private beta, merge, or deployment. Those decisions require separate explicit approval.
