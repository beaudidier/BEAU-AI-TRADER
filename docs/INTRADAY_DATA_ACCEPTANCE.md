# Intraday Data Acceptance

Generated: 2026-07-28T09:25:49.039404+00:00

## Executive verdict

**Overall: NOT YET ACCEPTED FOR LIVE DAY TRADING.**

The replay, aggregation, historical pagination and local recovery foundation
pass. The five complete sessions in this audit
were reconstructed from Alpaca's historical IEX REST endpoints, not captured
through five uninterrupted live WebSocket connections. Therefore
live-transport acceptance remains **INSUFFICIENT LIVE MULTI-DAY EVIDENCE** and the
day-trading foundation must remain research/paper-only.

No strategy, recommendation, production deployment or live-money execution was
introduced.

## Scope and methodology

- Dates: 2026-07-21, 2026-07-22, 2026-07-23, 2026-07-24, 2026-07-27
- Session window: 04:00–20:00 America/New_York
- Symbols: AAPL, NVDA, SPY, AMD, TSLA, META, MSFT, AMZN, PLTR, QQQ
- Source: Alpaca IEX (`partial-market`)
- Collection: fully paginated historical trades, quotes, 1m, 5m and 15m bars
- Raw recordings: append-only gzip NDJSON, stored locally and ignored by Git
- Replay: three streaming deterministic passes per session
- Acceptance duration represented: 80.0 hours

Alpaca documents IEX as a single-exchange feed suitable for initial testing,
not full US-market liquidity. Historical endpoints support explicit time
ranges, feed selection and pagination:

- https://docs.alpaca.markets/us/docs/historical-stock-data-1
- https://docs.alpaca.markets/us/reference/stockquotes-1
- https://docs.alpaca.markets/us/reference/stocktradesingle-1
- https://docs.alpaca.markets/us/v1.4.2/reference/stockbars

## Aggregate results

- Sessions: 5
- Events: 59,234,124
- Quotes: 58,041,608
- Trades: 1,167,197
- Provider 1m bars: 19,701
- API requests: 5,940
- Retries: 0
- Live reconnects observed in historical sessions: not measurable
- Simulated reconnect scenarios failed: 0
- Duplicate source events: 0
- Out-of-order events: 0
- Silent event loss: 0
- Checksum failures: 0
- Unexplained bar mismatches: 0
- Explained published-1m VWAP information-loss differences: 5,302
- Boundary violations: 0
- Real or Alpaca paper orders submitted: 0

## Session results

| Market date | Events | Quotes | Trades | 1m bars | Recorder gaps | Unexplained mismatches | 3× deterministic |
|---|---:|---:|---:|---:|---:|---:|---|
| 2026-07-21 | 8,252,328 | 8,064,266 | 182,960 | 3,966 | 78 | 0 | PASS |
| 2026-07-22 | 9,192,054 | 8,978,377 | 208,608 | 3,919 | 121 | 0 | PASS |
| 2026-07-23 | 13,334,458 | 13,059,204 | 270,104 | 3,997 | 86 | 0 | PASS |
| 2026-07-24 | 12,991,682 | 12,746,946 | 239,743 | 3,896 | 66 | 0 | PASS |
| 2026-07-27 | 15,463,602 | 15,192,815 | 265,782 | 3,923 | 26 | 0 | PASS |

## Bar integrity

Provider 1m bars were reconstructed from condition-aware raw trades. Alpaca's
published condition rules were used to explain minutes containing only trades
that cannot update bar prices. Direct 5m and 15m provider bars were compared
with condition-aware aggregates rebuilt from raw trades. Differences caused
only by the fact that published 1m bars omit the internal VWAP-eligible volume
denominator are reported separately as explained information loss.

Alpaca notes that the strictest trade condition controls whether open/close,
high/low and volume are updated, and a bar is not emitted if required price
fields remain zero:

https://docs.alpaca.markets/us/docs/market-data-faq

Condition-only missing minutes are reported separately and are not silently
classified as data loss.

## Session-boundary verification

The audit checked premarket→regular and regular→after-hours transitions using
timezone-aware America/New_York timestamps. Automated tests also cover DST and
the 13:00 ET early close. No multi-minute bar may cross a session boundary.

## Resilience verification

| Scenario | Status | Evidence |
|---|---|---|
| WebSocket disconnect/reconnect | PASS | Focused stream lifecycle and reconnect tests |
| Process restart | PASS | Append-only recorder recovery test |
| Temporary network outage | PASS | Bounded retry/backoff fault-injection test |
| Duplicated packets | PASS | Duplicate dispositions remain audit-visible |
| Delayed/out-of-order packets | PASS | Out-of-order dispositions remain audit-visible |
| Corrupted checkpoint | PASS | Checkpoint quarantined and pagination restarted |
| Storage interruption | PASS | Failed write does not advance append-only ledger |

These are deterministic fault-injection tests. The five historical sessions do
not prove real reconnect frequency or actual network-loss behaviour across five
live days.

## IEX coverage limitations

- IEX is partial-market coverage and must never be described as SIP or
  full-market data.
- Quote-only minutes, sparse-trade symbols, stale intervals and spread
  distributions are stored per session in the JSON artifact.
- Historical REST receipt timestamps are deterministic derived timestamps:
  quote/trade time equals provider time; provider bars become available only
  after their interval closes.
- Historical REST data cannot prove live WebSocket receipt latency, disconnect
  rate or packet loss.

## Acceptance decision

Data/replay acceptance: **PASS**

Live WebSocket multi-session acceptance: **INSUFFICIENT LIVE MULTI-DAY EVIDENCE**

Overall production readiness: **NOT YET ACCEPTED FOR LIVE DAY TRADING**

The foundation is suitable for continued isolated research and paper replay.
It is not approved for strategy claims, production deployment, live
recommendations or real-money execution. Five complete live WebSocket session
captures are still required to upgrade live-transport acceptance.
