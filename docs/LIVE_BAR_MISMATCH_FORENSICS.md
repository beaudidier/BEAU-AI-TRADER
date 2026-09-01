# Live Bar Mismatch Forensics

## Executive verdict

**FAIL. Milestone 57 remains failed.** All 124 previously unexplained items now
have a deterministic forensic classification, but the evidence does not prove
zero silent event loss. Twelve expected one-minute bar events are absent without
an overlapping reconnect marker. The acceptance criterion was not relaxed.

This work is paper/research-only on `feature/day-trading-foundation`. It changed
no trading strategy, order path, recommendation, production deployment, or
private-beta behavior. No Alpaca paper or real order was submitted.

## Evidence set

The audit read the immutable, checksum-valid recordings from:

- `live-iex-20260819`
- `live-iex-20260820`
- `live-iex-20260831`

Together they contain 26,309,248 events over 48 complete hours. Every mismatch
was linked to its raw trades, quotes, provider bar, receipt timestamps, provider
timestamps, trade conditions, exchange codes, duplicate dispositions, and
nearby stream lifecycle events. The detailed ledger is stored in
`artifacts/live_bar_mismatch_ledger.json`.

## Root-cause results

| Classification | Count | Evidence |
|---|---:|---|
| Reconnect/backfill boundary issue | 68 | 43 partial trade reconstructions, 20 missing provider bars, and 5 provider bars without raw trades overlap an auditable stale/disconnect/reconnect window. The live recorder had no REST event backfill. |
| Late trade arrival | 26 | A trade was received after the nominal minute close or initial bar calculation. Alpaca documents a separate `updatedBars` channel for these revisions; it was not subscribed. |
| Initial-stream-bar versus revised-bar semantics | 18 | No tested deterministic condition filter reproduces the initial streamed bar. The recording omitted `updatedBars`, corrections, and cancel/error channels, so a final provider revision cannot be reconstructed from this evidence. |
| Raw bar-event loss | 12 | Price-eligible trades require a bar under Alpaca's documented rules, but no bar event exists and no reconnect lifecycle event explains the omission. All 12 occurred on 2026-08-31 in four- or seven-symbol clusters. |
| Unknown | 0 | Every item is assigned to a reproducible failure mode or a specifically bounded provider-semantic ambiguity. |

Breakdown by session:

| Session | Total | Reconnect | Late arrival | Stream semantics | Raw event loss |
|---|---:|---:|---:|---:|---:|
| 2026-08-19 | 28 | 18 | 7 | 3 | 0 |
| 2026-08-20 | 36 | 23 | 6 | 7 | 0 |
| 2026-08-31 | 60 | 27 | 13 | 8 | 12 |

All 124 mismatches are one-minute items:

- 87 trade-to-provider reconstruction mismatches
- 32 missing provider bars despite price-eligible raw trades
- 5 provider bars without any recorded raw trade
- 0 five-minute aggregation mismatches
- 0 fifteen-minute aggregation mismatches

## Provider semantics

Alpaca states that minute bars are built from trades using tape-, condition-,
and bar-type-specific field update rules. Multiple conditions use the strictest
rule. A bar is emitted only when open, high, low, close, and volume are non-zero.
The rules also explain why an odd-lot-only minute can have volume activity but no
bar. See the official [Market Data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq).

Alpaca separately documents that late trades can revise an already emitted
minute through the `updatedBars` channel, normally after the half-minute mark.
The initial capture subscribed to `trades`, `quotes`, and `bars`, but not
`updatedBars`, `corrections`, or `cancelErrors`. See [Real-time Stock
Data](https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data) and the
[WebSocket subscription schema](https://docs.alpaca.markets/us/docs/streaming-market-data).

This missing revision evidence is not relabeled as acceptable. It is the exact
reason 18 items remain a provider-semantic ambiguity and why the initial bar
cannot be treated as a validated final bar.

## Candidate reconstructions

Every candidate was evaluated against every recorded one-minute interval, not
only against the 124 failed intervals. This prevents a filter from appearing to
help by creating failures elsewhere.

| Candidate | Existing mismatches resolved | New mismatches introduced | Total mismatches |
|---|---:|---:|---:|
| All raw trades | 0 | 11,091 | 11,215 |
| Exclude odd lots | 0 | 10,686 | 10,810 |
| Existing provider-condition rules | 0 | 0 | 124 |
| Existing rules with duplicate identities removed | 0 | 0 | 124 |
| Deduplicated events through initial provider-bar receipt | 8 | 0 | 116 |

The all-trade and odd-lot-only variants are decisively invalid. They create more
than ten thousand new discrepancies. The existing condition rules remain the
best-supported reconstruction and matched the earlier historical REST evidence,
but they cannot repair missing or non-final WebSocket evidence.

Correction/cancel and auction candidates cannot be honestly completed from
these files: the recorder did not subscribe to corrections or cancel/error
events, and no auction-specific condition explains the failed intervals. They
remain explicitly **not testable**, rather than being assumed absent. The next
recording must capture those channels before either candidate can be accepted or
rejected.

## Timing analysis

The tested local finalization cutoffs produced:

| Receipt cutoff after minute close | Mismatches resolved | Mismatches remaining |
|---|---:|---:|
| 0 seconds | 26 | 98 |
| 1 second | 8 | 116 |
| 2 seconds | 8 | 116 |
| 5 seconds | 8 | 116 |
| 10 seconds | 8 | 116 |
| 30 seconds | 0 | 124 |

Waiting longer while comparing against only the initial provider bar makes the
comparison worse: it incorporates late trades that belong in a later
`updatedBars` revision. Therefore this evidence does **not** justify changing
the current finalization delay. Correct validation requires the revision
channel, not an arbitrary larger delay.

The ledger stores both provider-to-receipt latency and lateness relative to the
minute close for every item. The 2026-08-31 market-open cluster reached more than
11 seconds of receipt lag across several symbols, while quote and trade traffic
continued. This is consistent with a slow-consumer/provider-channel ambiguity,
but the existing capture does not contain enough channel-level evidence to
assign which side omitted the bar.

## Reconnect and recovery findings

The 68 reconnect-related items are visible and auditable; they are not silent.
The exact stream lifecycle events are attached to each ledger row. The recorder
did not perform raw-event backfill after reconnect, so a deterministic replay can
reproduce the incomplete input perfectly while still failing data completeness.

This explains why deterministic replay and valid checksums did not make
Milestone 57 pass: both prove that the recorded bytes are stable, not that every
provider event reached the recording.

## Implementation audit

One research-verifier defect was proven: the Milestone 57 offline auditor
included events whose recorder disposition was `duplicate`. The auditor now
skips duplicate market events while retaining their diagnostic count. A focused
regression test proves the corrected behavior.

Removing duplicate identities alone resolved **0 of the 124 real-session
mismatches**, so this defect did not change the root-cause counts or the FAIL
verdict. Production stream aggregation and trading behavior were not modified.

## Required next evidence

The smallest valid next experiment is one additional high-volume market-open
recording on the same branch that:

1. captures `bars`, `updatedBars`, `corrections`, and `cancelErrors` together;
2. writes through a bounded asynchronous buffer with explicit slow-consumer
   telemetry;
3. records subscription acknowledgements for every channel;
4. backfills and reconciles each reconnect interval without overwriting raw
   evidence; and
5. reruns the same frozen 124-item forensic comparisons.

No heuristic aggregation change is justified before that evidence exists.

## Final acceptance decision

- Every mismatch has a forensic classification: **yes**
- Unknown mismatches: **0**
- Silent-loss absence proven: **no**
- Criteria relaxed: **no**
- Milestone 57 verdict after this audit: **FAIL**
- Milestone 58 forensic acceptance verdict: **FAIL**

The foundation remains research-only. Alpaca IEX represents partial-market
coverage and must not be presented as full US-market liquidity.
