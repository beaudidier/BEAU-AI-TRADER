# Production-Path Historical Replay

## Executive result

- Replay date: **2026-07-23**
- Frozen strategy: **regime-gated-pullback-v1.0.0**
- Production runner: **forward-validation-runner-v1.0.0**
- Symbols requested: **10**
- Symbols completed: **10**
- Symbols failed: **0**
- Signals found: **0**
- Rejected setups: **10**
- Duplicate requests prevented: **0**
- Production/standalone mismatches: **0**
- Live production tables unchanged: **YES**

This replay used real completed daily OHLCV data and the registered production `swing_trading` strategy. Every ticker history and SPY benchmark was cut off at the replay session before the signal calculation, so no later candle was available to either calculation.

## Universe accounting

- Requested: MU, NVDA, AMD, TSLA, AAPL, MSFT, META, AMZN, GOOGL, PLTR
- Completed: MU, NVDA, AMD, TSLA, AAPL, MSFT, META, AMZN, GOOGL, PLTR
- Failed: None

## Per-symbol audit

| Ticker | Result | Raw timestamp | Regime | Confidence | EMA20 entry | Swing low | Stop | TP1 | TP2 | Expiry | Comparison |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| MU | rejected | 2026-07-23T00:00:00 | 90.0 | 70.0 | 961.683548 | 804.0 | 683.032673 | 1520.427825 | 2078.691259 | — | MATCH |
| NVDA | rejected | 2026-07-23T00:00:00 | 90.0 | 71.0 | 205.759435 | 189.800003 | 178.902175 | 259.782594 | 313.702874 | — | MATCH |
| AMD | rejected | 2026-07-23T00:00:00 | 90.0 | 72.0 | 527.770812 | 460.209991 | 404.909241 | 774.28561 | 1020.536523 | — | MATCH |
| TSLA | rejected | 2026-07-23T00:00:00 | 90.0 | 56.0 | 385.422977 | 315.73999 | 287.133041 | 582.580982 | 779.546275 | — | MATCH |
| AAPL | rejected | 2026-07-23T00:00:00 | 90.0 | 73.0 | 316.127168 | 273.75 | 261.873553 | 425.108587 | 533.931943 | — | MATCH |
| MSFT | rejected | 2026-07-23T00:00:00 | 90.0 | 39.0 | 390.115161 | 349.200012 | 331.055154 | 508.820346 | 627.330474 | — | MATCH |
| META | rejected | 2026-07-23T00:00:00 | 90.0 | 49.0 | 625.082771 | 540.179993 | 502.449645 | 871.286648 | 1117.177984 | — | MATCH |
| AMZN | rejected | 2026-07-23T00:00:00 | 90.0 | 55.0 | 244.962537 | 225.550003 | 214.299775 | 306.655507 | 368.225994 | — | MATCH |
| GOOGL | rejected | 2026-07-23T00:00:00 | 90.0 | 63.0 | 351.966518 | 314.899994 | 296.568634 | 463.290235 | 574.437968 | — | MATCH |
| PLTR | rejected | 2026-07-23T00:00:00 | 90.0 | 34.0 | 129.211657 | 106.370003 | 96.384007 | 195.060775 | 260.845287 | — | MATCH |

## Explanations

### MU — rejected

- Per-share risk 29.01% exceeded the frozen 5% maximum.

### NVDA — rejected

- Per-share risk 13.10% exceeded the frozen 5% maximum.

### AMD — rejected

- Per-share risk 23.32% exceeded the frozen 5% maximum.

### TSLA — rejected

- Per-share risk 25.54% exceeded the frozen 5% maximum.

### AAPL — rejected

- Per-share risk 17.20% exceeded the frozen 5% maximum.

### MSFT — rejected

- Per-share risk 15.18% exceeded the frozen 5% maximum.

### META — rejected

- Per-share risk 19.66% exceeded the frozen 5% maximum.

### AMZN — rejected

- Per-share risk 12.56% exceeded the frozen 5% maximum.

### GOOGL — rejected

- Per-share risk 15.78% exceeded the frozen 5% maximum.

### PLTR — rejected

- Per-share risk 25.44% exceeded the frozen 5% maximum.

## Provider failures

- None.

## Production versus standalone comparison

- All 10 completed ticker calculations matched their direct standalone calculations.

The comparison covers the decision plus signal timestamp, signal price, EMA20 pullback entry, expected fill, stop, TP1, TP2, market regime, confidence, strategy version, and raw data timestamp.
For rejected setups, candidate TP1 and TP2 levels are shown for arithmetic audit only. The production strategy correctly does not emit them as executable chart levels after a rejection rule fires.

## Live-table immutability proof

| Table | Rows before | Rows after | Hash unchanged |
|---|---:|---:|---|
| forward_validation_runs | 6 | 6 | YES |
| forward_validation_signals | 0 | 0 | YES |
| forward_validation_outcomes | 0 | 0 | YES |
| paper_trades | 0 | 0 | YES |

Replay output was written only to the audit artifact and this report. The replay module exposes no insert, update, upsert, delete, paper-trade, or signal-store operation.

## Limitations

- This verifies deterministic signal generation on one completed market session, not future profitability.
- Candidate TP1 and TP2 values for rejected setups are diagnostic only; no production signal or executable chart level was created.
- Yahoo Finance remains a development data source and can return temporary provider errors.
