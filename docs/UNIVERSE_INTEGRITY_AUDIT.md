# Universe Integrity and Completeness Audit

## Executive result

| Universe | Previous | Expected | Actual | Duplicates | Invalid | Stale/delisted | Missing | Market-data failures | Health |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Demo 10 | 10 | 10 | 10 | 0 | 0 | 0 | 0 | 0 | healthy |
| Dow 30 | 30 | 30 | 30 | 0 | 0 | 0 | 0 | 0 | healthy |
| Nasdaq 100 | 30 | 103 | 103 | 0 | 0 | 0 | 0 | 0 | healthy |
| S&P 500 | 51 | 503 | 503 | 0 | 0 | 0 | 0 | 0 | healthy |
| All US Stocks | 71 | 5605 | 5605 | 0 | 0 | 0 | 0 | 1 | degraded |

## Provider availability

- Provider: **Yahoo Finance**
- Validated: **2026-07-25T14:33:26.025570+00:00**
- Symbols checked: **5605**
- Symbols available: **5604**
- Symbols unavailable after retry: **1**
- Method: Yahoo Finance adjusted 5-day daily history; missing symbols retried in smaller batches

Unavailable symbols:

- `SVA`

## Constituent sources

| Universe | Source | Source timestamp | Snapshot hash |
|---|---|---|---|
| Demo 10 | BEAU AI Trader configured demo list | 2026-07-25T14:30:41.340469+00:00 | `9953a90c62431aa2b001174b828bb58299c77000e47e15241c9f5546f601c40d` |
| Dow 30 | Wikipedia — Dow Jones Industrial Average constituents | 2026-07-23T10:49:37Z | `35dc0f1f03a02c10bb0a5ab1fcf6a6cbc5cd357a1942372811c6ff2ed361e5dd` |
| Nasdaq 100 | Wikipedia — List of Nasdaq-100 companies | 2026-07-22T01:09:33Z | `87efe7cf3d19998298a263ab327aa218121e80156b2680e2a205f329936a8839` |
| S&P 500 | Wikipedia — List of S&P 500 companies | 2026-07-21T06:56:32Z | `2c898ed66f9ec03fc3737ad9982772b4edc10c4a2abb1e6f6126a19c5af5b3c6` |
| All US Stocks | Nasdaq Trader daily Nasdaq and other-exchange symbol directories | 2026-07-24T21:31:00-04:00 | `bb4bc6c1aacbe2c92ce6259e7f5cce7fd97bf876e0887f3698b7c24250c7ba55` |

## Per-universe exceptions

### Demo 10

- Duplicates: None
- Invalid tickers: None
- Delisted or stale tickers: None
- Missing tickers: None
- Unavailable market data: None
- Missing from the previous truncated snapshot: **0**
- Previous missing examples: None
- Previous symbols no longer current: None

### Dow 30

- Duplicates: None
- Invalid tickers: None
- Delisted or stale tickers: None
- Missing tickers: None
- Unavailable market data: None
- Missing from the previous truncated snapshot: **1**
- Previous missing examples: `GOOGL`
- Previous symbols no longer current: INTC

### Nasdaq 100

- Duplicates: None
- Invalid tickers: None
- Delisted or stale tickers: None
- Missing tickers: None
- Unavailable market data: None
- Missing from the previous truncated snapshot: **73**
- Previous missing examples: `ABNB`, `ADI`, `ADSK`, `AEP`, `ALAB`, `ALNY`, `APP`, `ARM`, `ASML`, `AXON`, `BKR`, `CCEP`, `CDNS`, `CEG`, `CPRT`, `CRWD`, `CRWV`, `CSX`, `CTAS`, `DASH`, `DDOG`, `DXCM`, `EA`, `EXC`, `FANG` …
- Previous symbols no longer current: None

### S&P 500

- Duplicates: None
- Invalid tickers: None
- Delisted or stale tickers: None
- Missing tickers: None
- Unavailable market data: None
- Missing from the previous truncated snapshot: **452**
- Previous missing examples: `A`, `ABNB`, `ACGL`, `ADI`, `ADM`, `ADP`, `ADSK`, `AEE`, `AEP`, `AES`, `AFL`, `AIG`, `AIZ`, `AJG`, `AKAM`, `ALB`, `ALGN`, `ALL`, `ALLE`, `AMAT`, `AMCR`, `AME`, `AMP`, `AMT`, `ANET` …
- Previous symbols no longer current: None

### All US Stocks

- Duplicates: None
- Invalid tickers: None
- Delisted or stale tickers: None
- Missing tickers: None
- Unavailable market data: SVA
- Missing from the previous truncated snapshot: **5534**
- Previous missing examples: `A`, `AA`, `AACB`, `AACG`, `AACI`, `AACO`, `AACP`, `AADX`, `AAL`, `AAME`, `AAMI`, `AAOI`, `AAON`, `AAP`, `AAPG`, `AARD`, `AAT`, `AAUC`, `ABAT`, `ABCB`, `ABCL`, `ABEO`, `ABEV`, `ABG`, `ABLV` …
- Previous symbols no longer current: None

## Update mechanism

- Runtime scans use only `backend/universe/data/stock_universes.json`.
- `python -m universe.update_constituents` performs an explicit refresh.
- Index tables are validated against count ranges and the current Nasdaq Trader US listing directory.
- Symbols are normalized for Yahoo Finance before deduplication (`BRK.B` becomes `BRK-B`).
- A temporary file is atomically promoted only after every source validates.
- A failed refresh leaves the committed snapshot unchanged as the deterministic fallback.
