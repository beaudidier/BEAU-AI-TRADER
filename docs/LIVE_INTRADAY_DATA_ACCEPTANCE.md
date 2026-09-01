# Live Intraday Data Acceptance

Generated: 2026-09-01T09:53:28.532692+00:00

## Verdict

**FAIL**

This is an isolated paper/research validation of Alpaca IEX WebSocket data.
IEX is partial-market coverage and is not full US-market liquidity. No real or
Alpaca paper orders are submitted by this runner.

## Scope

- Required complete sessions: 3
- Complete sessions recorded: 3
- Window: 04:00–20:00 America/New_York
- Symbols: AAPL, NVDA, SPY, AMD, TSLA, META, MSFT, AMZN, PLTR, QQQ
- Raw recordings: local and Git-ignored
- Replay passes: three per completed session

## Results

| Date | Events | Reconnects | Gaps | Unexplained mismatches | Replay |
|---|---:|---:|---:|---:|---|
| 2026-08-19 | 10,790,089 | 458 | 60 | 28 | PASS |
| 2026-08-20 | 9,860,139 | 311 | 86 | 36 | PASS |
| 2026-08-31 | 5,659,020 | 269 | 118 | 60 | PASS |

- Total events: 26,309,248
- Total captured duration: 48.0 hours
- Reconnects: 1038
- Recorded gap diagnostics: 264
- Duplicate events: 667
- Out-of-order events: 0
- Unexplained mismatches: 124
- Session-boundary violations: 0
- Checksums valid: yes
- 5m/15m aggregation deterministic: yes
- Scheduled reconnect recovery observed: yes
- Silent-event-loss status: NOT_PROVEN
- Orders submitted: 0

## Unresolved evidence

| Date | Trade reconstruction | Missing provider bars | Provider bars without raw trades |
|---|---:|---:|---:|
| 2026-08-19 | 20 | 4 | 4 |
| 2026-08-20 | 26 | 10 | 0 |
| 2026-08-31 | 41 | 18 | 1 |

The 124 unresolved items consist of provider 1-minute bars that cannot be
reconciled exactly to the recorded IEX trade stream. The derived 5-minute and
15-minute aggregation replays themselves were identical across all three runs.
Because the unexplained items remain, this audit cannot claim zero silent event
loss even though every stored-file checksum is valid.

## Resilience and continuity

- A scheduled WebSocket disconnect was requested once in every session.
- Each session continued to its frozen 20:00 New York boundary and finalised.
- Reconnects, stale-stream timeouts, duplicates and gap diagnostics remain in
  the immutable local ledger; none were silently discarded.
- Provider subscription acknowledgements and reconnect events were captured.
- Event timestamps produced zero out-of-order classifications and no bar crossed
  a market-session boundary.

## Acceptance finding

The foundation does not pass acceptance. Replay and checksums may be deterministic while provider-bar reconstruction still contains unresolved evidence. Frozen failures: unexplained_mismatches:124.

## Acceptance rules

Acceptance requires three complete live sessions, deterministic replay, zero
unexplained aggregation mismatches and correct session boundaries. Disconnects,
timeouts and provider gaps must remain explicit in the audit ledger. This
evidence does not authorize live-money trading, strategy recommendations,
deployment or merging PR #2.
