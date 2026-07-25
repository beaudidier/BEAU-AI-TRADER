# Signal Availability Audit

## Executive verdict

The frozen Regime-Gated Pullback strategy was replayed through the registered production strategy interface for each of the most recent **60** completed US sessions (2026-04-28 through 2026-07-23).

| Configured universe | Names | Valid signals | Signals/day | Zero-signal days | Valid/week | Estimated weeks to 100 completed |
|---|---:|---:|---:|---:|---:|---:|
| Demo 10 | 10 | 1 | 0.017 | 59 (98.33%) | 0.083 | n/a |
| Dow 30 | 30 | 43 | 0.717 | 23 (38.33%) | 3.583 | 44.3 |
| Nasdaq 100 | 103 | 208 | 3.467 | 0 (0.00%) | 17.333 | 10.0 |
| S&P 500 | 503 | 565 | 9.417 | 0 (0.00%) | 47.083 | 3.9 |

The estimate to 100 completed trades uses the observed completion rate only for signals with enough later candles for the full entry and holding window. It is an availability estimate, not a performance forecast.

The index memberships come from the committed, timestamped constituent snapshot. Runtime scans read that snapshot and do not scrape public sources.

## Change from the truncated-universe audit

| Universe | Previous names | Corrected names | Previous signals | Corrected signals | Previous zero days | Corrected zero days |
|---|---:|---:|---:|---:|---:|---:|
| Demo 10 | 10 | 10 | 1 | 1 | 59 | 59 |
| Dow 30 | 30 | 30 | 77 | 43 | 24 | 23 |
| Nasdaq 100 | 30 | 103 | 106 | 208 | 24 | 0 |
| S&P 500 | 51 | 503 | 114 | 565 | 23 | 0 |

**Conclusion change:** Completing the Nasdaq-100 and S&P 500 universes eliminated zero-signal days in this window and materially shortened the estimated time to 100 completed trades. The prior conclusions that Demo 10 is too small, the 5% calculation is correct, and the frozen stop geometry is structurally wide relative to that cap did not change.

## Direct findings

- Stop formula arithmetic bug: **NO**
- Stop geometry structurally wide relative to the 5% cap in this window: **YES**. In the largest configured snapshot (S&P 500), 29375 of 29940 completed scans breached the 5% cap. The median rejected risk was 11.19%, decomposed into a 6.65% entry-to-swing-low distance and a 4.43% ATR buffer. The stop formula is therefore structurally wide relative to the frozen cap in this window, but it is not being calculated incorrectly.
- Demo universe too small for practical signal availability: **YES**
- 5% rule functioning as implemented: **YES**
- Frozen strategy naturally selective in this window: **YES**
- Volatility dependence: The risk gate rejected 100% of high-ATR observations in every configured universe; low-ATR observations had materially lower rejection rates in the larger snapshots.
- Regime dependence: Not identifiable from this 60-session sample because every audited session was classified Strong risk-on.

## Calculation integrity

- Production/standalone mismatches: **0**
- Risk observations checked: **30660**
- Maximum formula error: **0.0000113591 percentage points**
- Calculation bug found: **NO**
- Formula: `risk% = ((expected executable entry - (20-session swing low - 1.5 * ATR)) / expected executable entry) * 100`
- Decomposition: `risk% = distance from executable entry to swing low% + 1.5 * ATR%`

The executable entry includes the production entry slippage. The stop is the signal-time 20-session swing low minus the frozen 1.5 ATR buffer. Every history was limited to the production two-year window and sliced at the signal date before the registered strategy was called.

## Universe findings

### Demo 10

- Configured names: **10**
- Completed symbol/date scans: **600**
- Valid signals: **1**
- Rejected setups: **599**
- Provider failures: **0**
- Symbols without the required historical window: none
- Signals per trading day: **0.0167**
- Zero-signal frequency: **98.33%**
- Average valid signals per week: **0.0833**
- Mature signals used for outcome estimate: **1**
- Mature signal completion rate: **0.00%**
- Estimated weeks to issue 100 signals: **1200.0**
- Estimated weeks to 100 completed trades: **n/a**
- Rejection reasons: `risk_above_5_percent` 599

5% risk-limit distribution:

- Total risk-limit rejections: **599**
- Only slightly above 5% (greater than 5% through 7.5%): **16**
- Above 7.5%: **583**
- Above 10%: **518**
- Median rejected risk: **14.06%**
- Median entry-to-swing-low distance: **8.47%**
- Median 1.5 ATR buffer: **5.21%**
- Largest rejection sector: **Technology** (60.10%)
- One-sector dominance (>50%): **YES**

Risk-limit rejection rate by volatility:

| ATR bucket | Completed scans | Risk rejections | Rate |
|---|---:|---:|---:|
| High (>4% ATR) | 231 | 231 | 100.00% |
| Low (<2% ATR) | 7 | 7 | 100.00% |
| Moderate (2-4% ATR) | 362 | 361 | 99.72% |

Risk-limit rejection rate by market regime:

| Regime | Completed scans | Risk rejections | Rate |
|---|---:|---:|---:|
| Strong risk-on | 600 | 599 | 99.83% |

### Dow 30

- Configured names: **30**
- Completed symbol/date scans: **1800**
- Valid signals: **43**
- Rejected setups: **1757**
- Provider failures: **0**
- Symbols without the required historical window: none
- Signals per trading day: **0.7167**
- Zero-signal frequency: **38.33%**
- Average valid signals per week: **3.5833**
- Mature signals used for outcome estimate: **27**
- Mature signal completion rate: **62.96%**
- Estimated weeks to issue 100 signals: **27.9**
- Estimated weeks to 100 completed trades: **44.3**
- Rejection reasons: `risk_above_5_percent` 1757

5% risk-limit distribution:

- Total risk-limit rejections: **1757**
- Only slightly above 5% (greater than 5% through 7.5%): **349**
- Above 7.5%: **1408**
- Above 10%: **893**
- Median rejected risk: **10.04%**
- Median entry-to-swing-low distance: **5.99%**
- Median 1.5 ATR buffer: **3.91%**
- Largest rejection sector: **Financials** (16.90%)
- One-sector dominance (>50%): **NO**

Risk-limit rejection rate by volatility:

| ATR bucket | Completed scans | Risk rejections | Rate |
|---|---:|---:|---:|
| High (>4% ATR) | 178 | 178 | 100.00% |
| Low (<2% ATR) | 218 | 177 | 81.19% |
| Moderate (2-4% ATR) | 1404 | 1402 | 99.86% |

Risk-limit rejection rate by market regime:

| Regime | Completed scans | Risk rejections | Rate |
|---|---:|---:|---:|
| Strong risk-on | 1800 | 1757 | 97.61% |

### Nasdaq 100

- Configured names: **103**
- Completed symbol/date scans: **5880**
- Valid signals: **208**
- Rejected setups: **5672**
- Provider failures: **300**
- Symbols without the required historical window: `CRWV`, `HONA`, `NBIS`, `SNDK`, `SPCX`
- Signals per trading day: **3.4667**
- Zero-signal frequency: **0.00%**
- Average valid signals per week: **17.3333**
- Mature signals used for outcome estimate: **125**
- Mature signal completion rate: **57.60%**
- Estimated weeks to issue 100 signals: **5.8**
- Estimated weeks to 100 completed trades: **10.0**
- Rejection reasons: `risk_above_5_percent` 5672

5% risk-limit distribution:

- Total risk-limit rejections: **5672**
- Only slightly above 5% (greater than 5% through 7.5%): **618**
- Above 7.5%: **5054**
- Above 10%: **4070**
- Median rejected risk: **13.20%**
- Median entry-to-swing-low distance: **7.88%**
- Median 1.5 ATR buffer: **5.23%**
- Largest rejection sector: **Technology** (44.25%)
- One-sector dominance (>50%): **NO**

Risk-limit rejection rate by volatility:

| ATR bucket | Completed scans | Risk rejections | Rate |
|---|---:|---:|---:|
| High (>4% ATR) | 2264 | 2264 | 100.00% |
| Low (<2% ATR) | 484 | 277 | 57.23% |
| Moderate (2-4% ATR) | 3132 | 3131 | 99.97% |

Risk-limit rejection rate by market regime:

| Regime | Completed scans | Risk rejections | Rate |
|---|---:|---:|---:|
| Strong risk-on | 5880 | 5672 | 96.46% |

### S&P 500

- Configured names: **503**
- Completed symbol/date scans: **29940**
- Valid signals: **565**
- Rejected setups: **29375**
- Provider failures: **240**
- Symbols without the required historical window: `FDXF`, `HONA`, `Q`, `SNDK`
- Signals per trading day: **9.4167**
- Zero-signal frequency: **0.00%**
- Average valid signals per week: **47.0833**
- Mature signals used for outcome estimate: **361**
- Mature signal completion rate: **54.85%**
- Estimated weeks to issue 100 signals: **2.1**
- Estimated weeks to 100 completed trades: **3.9**
- Rejection reasons: `risk_above_5_percent` 29375

5% risk-limit distribution:

- Total risk-limit rejections: **29375**
- Only slightly above 5% (greater than 5% through 7.5%): **4346**
- Above 7.5%: **25029**
- Above 10%: **17771**
- Median rejected risk: **11.19%**
- Median entry-to-swing-low distance: **6.65%**
- Median 1.5 ATR buffer: **4.43%**
- Largest rejection sector: **Industrials** (15.65%)
- One-sector dominance (>50%): **NO**

Risk-limit rejection rate by volatility:

| ATR bucket | Completed scans | Risk rejections | Rate |
|---|---:|---:|---:|
| High (>4% ATR) | 6288 | 6288 | 100.00% |
| Low (<2% ATR) | 2999 | 2461 | 82.06% |
| Moderate (2-4% ATR) | 20653 | 20626 | 99.87% |

Risk-limit rejection rate by market regime:

| Regime | Completed scans | Risk rejections | Rate |
|---|---:|---:|---:|
| Strong risk-on | 29940 | 29375 | 98.11% |

## Per-date audit

Each row is the exact aggregate required for one configured universe and one completed session.

| Universe | Date | Scanned | Valid | Rejected | Failures | Regime | Median risk % | Median swing-low distance % | Median ATR % | Rejection reasons |
|---|---|---:|---:|---:|---:|---|---:|---:|---:|---|
| Demo 10 | 2026-04-28 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 19.79 | 15.53 | 2.92 | risk_above_5_percent:10 |
| Demo 10 | 2026-04-29 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 18.09 | 13.80 | 2.86 | risk_above_5_percent:10 |
| Demo 10 | 2026-04-30 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 18.55 | 13.78 | 3.25 | risk_above_5_percent:10 |
| Demo 10 | 2026-05-01 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 17.53 | 12.94 | 3.21 | risk_above_5_percent:10 |
| Demo 10 | 2026-05-04 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 17.62 | 13.08 | 3.17 | risk_above_5_percent:10 |
| Demo 10 | 2026-05-05 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 16.11 | 11.20 | 3.11 | risk_above_5_percent:10 |
| Demo 10 | 2026-05-06 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 16.58 | 11.99 | 3.22 | risk_above_5_percent:10 |
| Demo 10 | 2026-05-07 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 15.10 | 10.58 | 3.19 | risk_above_5_percent:10 |
| Demo 10 | 2026-05-08 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 14.65 | 9.34 | 3.13 | risk_above_5_percent:10 |
| Demo 10 | 2026-05-11 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 12.40 | 6.93 | 3.11 | risk_above_5_percent:10 |
| Demo 10 | 2026-05-12 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 11.97 | 6.94 | 3.10 | risk_above_5_percent:10 |
| Demo 10 | 2026-05-13 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 12.69 | 7.19 | 3.12 | risk_above_5_percent:10 |
| Demo 10 | 2026-05-14 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 13.16 | 7.17 | 3.11 | risk_above_5_percent:10 |
| Demo 10 | 2026-05-15 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 13.33 | 7.35 | 3.14 | risk_above_5_percent:10 |
| Demo 10 | 2026-05-18 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 13.50 | 7.70 | 3.18 | risk_above_5_percent:10 |
| Demo 10 | 2026-05-19 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 13.47 | 8.09 | 3.18 | risk_above_5_percent:10 |
| Demo 10 | 2026-05-20 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 13.56 | 8.55 | 3.13 | risk_above_5_percent:10 |
| Demo 10 | 2026-05-21 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 13.60 | 8.92 | 3.15 | risk_above_5_percent:10 |
| Demo 10 | 2026-05-22 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 13.15 | 9.22 | 3.09 | risk_above_5_percent:10 |
| Demo 10 | 2026-05-26 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 12.97 | 9.14 | 3.03 | risk_above_5_percent:10 |
| Demo 10 | 2026-05-27 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 13.05 | 9.36 | 3.01 | risk_above_5_percent:10 |
| Demo 10 | 2026-05-28 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 12.71 | 7.84 | 2.98 | risk_above_5_percent:10 |
| Demo 10 | 2026-05-29 | 10 | 1 | 9 | 0 | Strong risk-on (90) | 12.37 | 7.75 | 3.07 | risk_above_5_percent:9 |
| Demo 10 | 2026-06-01 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 12.48 | 8.32 | 3.19 | risk_above_5_percent:10 |
| Demo 10 | 2026-06-02 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 12.49 | 8.33 | 3.28 | risk_above_5_percent:10 |
| Demo 10 | 2026-06-03 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 11.95 | 7.16 | 3.33 | risk_above_5_percent:10 |
| Demo 10 | 2026-06-04 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 10.24 | 5.74 | 3.25 | risk_above_5_percent:10 |
| Demo 10 | 2026-06-05 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 10.58 | 5.74 | 3.54 | risk_above_5_percent:10 |
| Demo 10 | 2026-06-08 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 10.36 | 5.86 | 3.50 | risk_above_5_percent:10 |
| Demo 10 | 2026-06-09 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 11.88 | 6.74 | 3.56 | risk_above_5_percent:10 |
| Demo 10 | 2026-06-10 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 11.85 | 6.70 | 3.58 | risk_above_5_percent:10 |
| Demo 10 | 2026-06-11 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 12.31 | 7.65 | 3.54 | risk_above_5_percent:10 |
| Demo 10 | 2026-06-12 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 12.09 | 7.50 | 3.45 | risk_above_5_percent:10 |
| Demo 10 | 2026-06-15 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 11.99 | 7.36 | 3.54 | risk_above_5_percent:10 |
| Demo 10 | 2026-06-16 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 11.76 | 7.16 | 3.46 | risk_above_5_percent:10 |
| Demo 10 | 2026-06-17 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 11.87 | 6.84 | 3.53 | risk_above_5_percent:10 |
| Demo 10 | 2026-06-18 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 11.86 | 6.65 | 3.50 | risk_above_5_percent:10 |
| Demo 10 | 2026-06-22 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 12.46 | 6.90 | 3.47 | risk_above_5_percent:10 |
| Demo 10 | 2026-06-23 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 12.13 | 6.70 | 3.45 | risk_above_5_percent:10 |
| Demo 10 | 2026-06-24 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 11.86 | 6.88 | 3.39 | risk_above_5_percent:10 |
| Demo 10 | 2026-06-25 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 13.01 | 7.47 | 3.44 | risk_above_5_percent:10 |
| Demo 10 | 2026-06-26 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 13.40 | 7.76 | 3.46 | risk_above_5_percent:10 |
| Demo 10 | 2026-06-29 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 13.79 | 7.85 | 3.54 | risk_above_5_percent:10 |
| Demo 10 | 2026-06-30 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 13.89 | 8.06 | 3.45 | risk_above_5_percent:10 |
| Demo 10 | 2026-07-01 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 13.85 | 8.36 | 3.61 | risk_above_5_percent:10 |
| Demo 10 | 2026-07-02 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 13.83 | 8.26 | 3.70 | risk_above_5_percent:10 |
| Demo 10 | 2026-07-06 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 13.85 | 8.54 | 3.63 | risk_above_5_percent:10 |
| Demo 10 | 2026-07-07 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 14.04 | 8.62 | 3.65 | risk_above_5_percent:10 |
| Demo 10 | 2026-07-08 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 14.03 | 8.54 | 3.67 | risk_above_5_percent:10 |
| Demo 10 | 2026-07-09 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 14.61 | 8.83 | 3.83 | risk_above_5_percent:10 |
| Demo 10 | 2026-07-10 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 14.99 | 9.52 | 3.96 | risk_above_5_percent:10 |
| Demo 10 | 2026-07-13 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 14.89 | 9.14 | 3.93 | risk_above_5_percent:10 |
| Demo 10 | 2026-07-14 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 14.66 | 9.05 | 3.89 | risk_above_5_percent:10 |
| Demo 10 | 2026-07-15 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 14.86 | 9.17 | 3.89 | risk_above_5_percent:10 |
| Demo 10 | 2026-07-16 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 15.22 | 9.25 | 3.83 | risk_above_5_percent:10 |
| Demo 10 | 2026-07-17 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 15.54 | 11.22 | 3.94 | risk_above_5_percent:10 |
| Demo 10 | 2026-07-20 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 15.92 | 11.21 | 3.85 | risk_above_5_percent:10 |
| Demo 10 | 2026-07-21 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 16.08 | 11.47 | 3.73 | risk_above_5_percent:10 |
| Demo 10 | 2026-07-22 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 16.20 | 11.69 | 3.76 | risk_above_5_percent:10 |
| Demo 10 | 2026-07-23 | 10 | 0 | 10 | 0 | Strong risk-on (90) | 18.43 | 13.15 | 3.78 | risk_above_5_percent:10 |
| Dow 30 | 2026-04-28 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 10.98 | 7.61 | 2.48 | risk_above_5_percent:29 |
| Dow 30 | 2026-04-29 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 10.73 | 7.07 | 2.50 | risk_above_5_percent:29 |
| Dow 30 | 2026-04-30 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 10.83 | 7.13 | 2.61 | risk_above_5_percent:29 |
| Dow 30 | 2026-05-01 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 10.37 | 6.55 | 2.62 | risk_above_5_percent:29 |
| Dow 30 | 2026-05-04 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 10.27 | 6.51 | 2.61 | risk_above_5_percent:29 |
| Dow 30 | 2026-05-05 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 9.76 | 5.70 | 2.57 | risk_above_5_percent:28 |
| Dow 30 | 2026-05-06 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 9.58 | 5.72 | 2.58 | risk_above_5_percent:28 |
| Dow 30 | 2026-05-07 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 9.42 | 5.66 | 2.56 | risk_above_5_percent:28 |
| Dow 30 | 2026-05-08 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 9.33 | 5.52 | 2.52 | risk_above_5_percent:29 |
| Dow 30 | 2026-05-11 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 9.45 | 5.25 | 2.54 | risk_above_5_percent:29 |
| Dow 30 | 2026-05-12 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 8.78 | 4.99 | 2.53 | risk_above_5_percent:29 |
| Dow 30 | 2026-05-13 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 8.91 | 5.50 | 2.52 | risk_above_5_percent:29 |
| Dow 30 | 2026-05-14 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 8.71 | 5.19 | 2.44 | risk_above_5_percent:29 |
| Dow 30 | 2026-05-15 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 8.32 | 4.97 | 2.47 | risk_above_5_percent:29 |
| Dow 30 | 2026-05-18 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 8.59 | 4.98 | 2.46 | risk_above_5_percent:30 |
| Dow 30 | 2026-05-19 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 8.53 | 5.40 | 2.48 | risk_above_5_percent:30 |
| Dow 30 | 2026-05-20 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 8.55 | 5.34 | 2.55 | risk_above_5_percent:30 |
| Dow 30 | 2026-05-21 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 9.35 | 5.40 | 2.57 | risk_above_5_percent:30 |
| Dow 30 | 2026-05-22 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 9.56 | 5.70 | 2.55 | risk_above_5_percent:30 |
| Dow 30 | 2026-05-26 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 9.44 | 5.60 | 2.56 | risk_above_5_percent:29 |
| Dow 30 | 2026-05-27 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 9.49 | 5.67 | 2.50 | risk_above_5_percent:30 |
| Dow 30 | 2026-05-28 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 8.79 | 4.99 | 2.47 | risk_above_5_percent:30 |
| Dow 30 | 2026-05-29 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 8.63 | 4.96 | 2.49 | risk_above_5_percent:29 |
| Dow 30 | 2026-06-01 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 8.66 | 4.95 | 2.48 | risk_above_5_percent:28 |
| Dow 30 | 2026-06-02 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 9.15 | 5.02 | 2.48 | risk_above_5_percent:28 |
| Dow 30 | 2026-06-03 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 9.38 | 5.40 | 2.54 | risk_above_5_percent:28 |
| Dow 30 | 2026-06-04 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 9.27 | 5.13 | 2.66 | risk_above_5_percent:29 |
| Dow 30 | 2026-06-05 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 9.15 | 4.97 | 2.63 | risk_above_5_percent:29 |
| Dow 30 | 2026-06-08 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 9.16 | 4.99 | 2.63 | risk_above_5_percent:29 |
| Dow 30 | 2026-06-09 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 9.12 | 5.09 | 2.66 | risk_above_5_percent:29 |
| Dow 30 | 2026-06-10 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 9.36 | 5.19 | 2.62 | risk_above_5_percent:29 |
| Dow 30 | 2026-06-11 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 9.76 | 5.48 | 2.69 | risk_above_5_percent:29 |
| Dow 30 | 2026-06-12 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 9.92 | 5.51 | 2.65 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-15 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 10.21 | 5.75 | 2.67 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-16 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 10.39 | 6.00 | 2.63 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-17 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 10.30 | 6.11 | 2.64 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-18 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 10.04 | 6.04 | 2.69 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-22 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 9.77 | 5.99 | 2.66 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-23 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 9.77 | 6.02 | 2.68 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-24 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 10.31 | 6.09 | 2.75 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-25 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 11.04 | 6.98 | 2.78 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-26 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 11.13 | 7.04 | 2.76 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-29 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 11.25 | 7.24 | 2.75 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-30 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 11.63 | 7.31 | 2.71 | risk_above_5_percent:30 |
| Dow 30 | 2026-07-01 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 11.93 | 7.32 | 2.72 | risk_above_5_percent:30 |
| Dow 30 | 2026-07-02 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 11.60 | 6.98 | 2.75 | risk_above_5_percent:30 |
| Dow 30 | 2026-07-06 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 11.42 | 7.07 | 2.76 | risk_above_5_percent:30 |
| Dow 30 | 2026-07-07 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 11.49 | 7.11 | 2.79 | risk_above_5_percent:29 |
| Dow 30 | 2026-07-08 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 11.64 | 6.91 | 2.80 | risk_above_5_percent:30 |
| Dow 30 | 2026-07-09 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 11.23 | 6.63 | 2.78 | risk_above_5_percent:29 |
| Dow 30 | 2026-07-10 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 10.81 | 6.69 | 2.69 | risk_above_5_percent:29 |
| Dow 30 | 2026-07-13 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 10.28 | 6.41 | 2.67 | risk_above_5_percent:29 |
| Dow 30 | 2026-07-14 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 9.93 | 6.01 | 2.62 | risk_above_5_percent:29 |
| Dow 30 | 2026-07-15 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 10.13 | 6.27 | 2.66 | risk_above_5_percent:29 |
| Dow 30 | 2026-07-16 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 10.50 | 6.77 | 2.73 | risk_above_5_percent:29 |
| Dow 30 | 2026-07-17 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 10.96 | 6.75 | 2.76 | risk_above_5_percent:29 |
| Dow 30 | 2026-07-20 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 10.66 | 6.47 | 2.80 | risk_above_5_percent:29 |
| Dow 30 | 2026-07-21 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 10.43 | 6.32 | 2.78 | risk_above_5_percent:29 |
| Dow 30 | 2026-07-22 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 9.78 | 5.81 | 2.71 | risk_above_5_percent:29 |
| Dow 30 | 2026-07-23 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 10.22 | 5.74 | 2.82 | risk_above_5_percent:29 |
| Nasdaq 100 | 2026-04-28 | 98 | 5 | 93 | 5 | Strong risk-on (90) | 14.47 | 10.07 | 3.16 | risk_above_5_percent:93 |
| Nasdaq 100 | 2026-04-29 | 98 | 6 | 92 | 5 | Strong risk-on (90) | 14.76 | 10.13 | 3.20 | risk_above_5_percent:92 |
| Nasdaq 100 | 2026-04-30 | 98 | 5 | 93 | 5 | Strong risk-on (90) | 14.83 | 10.30 | 3.26 | risk_above_5_percent:93 |
| Nasdaq 100 | 2026-05-01 | 98 | 6 | 92 | 5 | Strong risk-on (90) | 14.34 | 9.70 | 3.22 | risk_above_5_percent:92 |
| Nasdaq 100 | 2026-05-04 | 98 | 5 | 93 | 5 | Strong risk-on (90) | 14.81 | 9.60 | 3.17 | risk_above_5_percent:93 |
| Nasdaq 100 | 2026-05-05 | 98 | 5 | 93 | 5 | Strong risk-on (90) | 13.28 | 8.45 | 3.20 | risk_above_5_percent:93 |
| Nasdaq 100 | 2026-05-06 | 98 | 5 | 93 | 5 | Strong risk-on (90) | 13.52 | 8.53 | 3.26 | risk_above_5_percent:93 |
| Nasdaq 100 | 2026-05-07 | 98 | 5 | 93 | 5 | Strong risk-on (90) | 12.97 | 8.15 | 3.30 | risk_above_5_percent:93 |
| Nasdaq 100 | 2026-05-08 | 98 | 5 | 93 | 5 | Strong risk-on (90) | 13.19 | 8.25 | 3.33 | risk_above_5_percent:93 |
| Nasdaq 100 | 2026-05-11 | 98 | 6 | 92 | 5 | Strong risk-on (90) | 12.85 | 7.07 | 3.30 | risk_above_5_percent:92 |
| Nasdaq 100 | 2026-05-12 | 98 | 5 | 93 | 5 | Strong risk-on (90) | 12.69 | 7.19 | 3.27 | risk_above_5_percent:93 |
| Nasdaq 100 | 2026-05-13 | 98 | 5 | 93 | 5 | Strong risk-on (90) | 12.64 | 7.40 | 3.22 | risk_above_5_percent:93 |
| Nasdaq 100 | 2026-05-14 | 98 | 5 | 93 | 5 | Strong risk-on (90) | 12.38 | 7.17 | 3.21 | risk_above_5_percent:93 |
| Nasdaq 100 | 2026-05-15 | 98 | 5 | 93 | 5 | Strong risk-on (90) | 12.19 | 7.27 | 3.15 | risk_above_5_percent:93 |
| Nasdaq 100 | 2026-05-18 | 98 | 2 | 96 | 5 | Strong risk-on (90) | 12.66 | 7.37 | 3.23 | risk_above_5_percent:96 |
| Nasdaq 100 | 2026-05-19 | 98 | 2 | 96 | 5 | Strong risk-on (90) | 12.33 | 7.34 | 3.17 | risk_above_5_percent:96 |
| Nasdaq 100 | 2026-05-20 | 98 | 3 | 95 | 5 | Strong risk-on (90) | 12.55 | 7.24 | 3.31 | risk_above_5_percent:95 |
| Nasdaq 100 | 2026-05-21 | 98 | 3 | 95 | 5 | Strong risk-on (90) | 12.07 | 7.03 | 3.33 | risk_above_5_percent:95 |
| Nasdaq 100 | 2026-05-22 | 98 | 3 | 95 | 5 | Strong risk-on (90) | 12.13 | 7.29 | 3.38 | risk_above_5_percent:95 |
| Nasdaq 100 | 2026-05-26 | 98 | 2 | 96 | 5 | Strong risk-on (90) | 11.82 | 7.08 | 3.33 | risk_above_5_percent:96 |
| Nasdaq 100 | 2026-05-27 | 98 | 2 | 96 | 5 | Strong risk-on (90) | 12.03 | 6.57 | 3.35 | risk_above_5_percent:96 |
| Nasdaq 100 | 2026-05-28 | 98 | 3 | 95 | 5 | Strong risk-on (90) | 11.67 | 6.41 | 3.38 | risk_above_5_percent:95 |
| Nasdaq 100 | 2026-05-29 | 98 | 4 | 94 | 5 | Strong risk-on (90) | 11.67 | 7.00 | 3.33 | risk_above_5_percent:94 |
| Nasdaq 100 | 2026-06-01 | 98 | 6 | 92 | 5 | Strong risk-on (90) | 11.91 | 7.29 | 3.37 | risk_above_5_percent:92 |
| Nasdaq 100 | 2026-06-02 | 98 | 6 | 92 | 5 | Strong risk-on (90) | 12.53 | 7.83 | 3.46 | risk_above_5_percent:92 |
| Nasdaq 100 | 2026-06-03 | 98 | 6 | 92 | 5 | Strong risk-on (90) | 12.77 | 7.51 | 3.42 | risk_above_5_percent:92 |
| Nasdaq 100 | 2026-06-04 | 98 | 6 | 92 | 5 | Strong risk-on (90) | 12.54 | 7.61 | 3.51 | risk_above_5_percent:92 |
| Nasdaq 100 | 2026-06-05 | 98 | 4 | 94 | 5 | Strong risk-on (90) | 12.43 | 7.43 | 3.56 | risk_above_5_percent:94 |
| Nasdaq 100 | 2026-06-08 | 98 | 4 | 94 | 5 | Strong risk-on (90) | 12.40 | 7.28 | 3.55 | risk_above_5_percent:94 |
| Nasdaq 100 | 2026-06-09 | 98 | 4 | 94 | 5 | Strong risk-on (90) | 12.70 | 7.57 | 3.57 | risk_above_5_percent:94 |
| Nasdaq 100 | 2026-06-10 | 98 | 4 | 94 | 5 | Strong risk-on (90) | 12.54 | 7.22 | 3.53 | risk_above_5_percent:94 |
| Nasdaq 100 | 2026-06-11 | 98 | 4 | 94 | 5 | Strong risk-on (90) | 12.31 | 7.39 | 3.56 | risk_above_5_percent:94 |
| Nasdaq 100 | 2026-06-12 | 98 | 1 | 97 | 5 | Strong risk-on (90) | 12.09 | 7.24 | 3.55 | risk_above_5_percent:97 |
| Nasdaq 100 | 2026-06-15 | 98 | 1 | 97 | 5 | Strong risk-on (90) | 12.04 | 7.31 | 3.52 | risk_above_5_percent:97 |
| Nasdaq 100 | 2026-06-16 | 98 | 1 | 97 | 5 | Strong risk-on (90) | 12.06 | 7.20 | 3.54 | risk_above_5_percent:97 |
| Nasdaq 100 | 2026-06-17 | 98 | 1 | 97 | 5 | Strong risk-on (90) | 11.91 | 7.13 | 3.53 | risk_above_5_percent:97 |
| Nasdaq 100 | 2026-06-18 | 98 | 1 | 97 | 5 | Strong risk-on (90) | 12.12 | 7.22 | 3.47 | risk_above_5_percent:97 |
| Nasdaq 100 | 2026-06-22 | 98 | 1 | 97 | 5 | Strong risk-on (90) | 11.92 | 6.68 | 3.41 | risk_above_5_percent:97 |
| Nasdaq 100 | 2026-06-23 | 98 | 1 | 97 | 5 | Strong risk-on (90) | 11.63 | 6.65 | 3.33 | risk_above_5_percent:97 |
| Nasdaq 100 | 2026-06-24 | 98 | 1 | 97 | 5 | Strong risk-on (90) | 11.44 | 6.42 | 3.32 | risk_above_5_percent:97 |
| Nasdaq 100 | 2026-06-25 | 98 | 1 | 97 | 5 | Strong risk-on (90) | 12.50 | 7.13 | 3.31 | risk_above_5_percent:97 |
| Nasdaq 100 | 2026-06-26 | 98 | 1 | 97 | 5 | Strong risk-on (90) | 12.74 | 7.30 | 3.45 | risk_above_5_percent:97 |
| Nasdaq 100 | 2026-06-29 | 98 | 1 | 97 | 5 | Strong risk-on (90) | 13.01 | 7.57 | 3.54 | risk_above_5_percent:97 |
| Nasdaq 100 | 2026-06-30 | 98 | 1 | 97 | 5 | Strong risk-on (90) | 12.94 | 7.69 | 3.45 | risk_above_5_percent:97 |
| Nasdaq 100 | 2026-07-01 | 98 | 1 | 97 | 5 | Strong risk-on (90) | 12.83 | 7.85 | 3.70 | risk_above_5_percent:97 |
| Nasdaq 100 | 2026-07-02 | 98 | 1 | 97 | 5 | Strong risk-on (90) | 12.90 | 8.01 | 3.66 | risk_above_5_percent:97 |
| Nasdaq 100 | 2026-07-06 | 98 | 1 | 97 | 5 | Strong risk-on (90) | 13.08 | 7.87 | 3.60 | risk_above_5_percent:97 |
| Nasdaq 100 | 2026-07-07 | 98 | 4 | 94 | 5 | Strong risk-on (90) | 13.23 | 8.00 | 3.53 | risk_above_5_percent:94 |
| Nasdaq 100 | 2026-07-08 | 98 | 2 | 96 | 5 | Strong risk-on (90) | 13.26 | 8.05 | 3.50 | risk_above_5_percent:96 |
| Nasdaq 100 | 2026-07-09 | 98 | 5 | 93 | 5 | Strong risk-on (90) | 13.36 | 8.36 | 3.48 | risk_above_5_percent:93 |
| Nasdaq 100 | 2026-07-10 | 98 | 5 | 93 | 5 | Strong risk-on (90) | 13.62 | 8.34 | 3.47 | risk_above_5_percent:93 |
| Nasdaq 100 | 2026-07-13 | 98 | 4 | 94 | 5 | Strong risk-on (90) | 13.51 | 8.05 | 3.39 | risk_above_5_percent:94 |
| Nasdaq 100 | 2026-07-14 | 98 | 4 | 94 | 5 | Strong risk-on (90) | 12.93 | 7.92 | 3.37 | risk_above_5_percent:94 |
| Nasdaq 100 | 2026-07-15 | 98 | 4 | 94 | 5 | Strong risk-on (90) | 13.49 | 8.10 | 3.44 | risk_above_5_percent:94 |
| Nasdaq 100 | 2026-07-16 | 98 | 4 | 94 | 5 | Strong risk-on (90) | 13.41 | 7.92 | 3.46 | risk_above_5_percent:94 |
| Nasdaq 100 | 2026-07-17 | 98 | 4 | 94 | 5 | Strong risk-on (90) | 14.60 | 8.98 | 3.60 | risk_above_5_percent:94 |
| Nasdaq 100 | 2026-07-20 | 98 | 4 | 94 | 5 | Strong risk-on (90) | 14.28 | 8.61 | 3.53 | risk_above_5_percent:94 |
| Nasdaq 100 | 2026-07-21 | 98 | 4 | 94 | 5 | Strong risk-on (90) | 14.51 | 8.54 | 3.42 | risk_above_5_percent:94 |
| Nasdaq 100 | 2026-07-22 | 98 | 4 | 94 | 5 | Strong risk-on (90) | 14.21 | 8.41 | 3.34 | risk_above_5_percent:94 |
| Nasdaq 100 | 2026-07-23 | 98 | 4 | 94 | 5 | Strong risk-on (90) | 14.78 | 8.41 | 3.61 | risk_above_5_percent:94 |
| S&P 500 | 2026-04-28 | 499 | 14 | 485 | 4 | Strong risk-on (90) | 12.12 | 7.65 | 2.83 | risk_above_5_percent:485 |
| S&P 500 | 2026-04-29 | 499 | 15 | 484 | 4 | Strong risk-on (90) | 11.68 | 7.21 | 2.86 | risk_above_5_percent:484 |
| S&P 500 | 2026-04-30 | 499 | 14 | 485 | 4 | Strong risk-on (90) | 11.92 | 7.41 | 2.89 | risk_above_5_percent:485 |
| S&P 500 | 2026-05-01 | 499 | 14 | 485 | 4 | Strong risk-on (90) | 11.36 | 6.84 | 2.87 | risk_above_5_percent:485 |
| S&P 500 | 2026-05-04 | 499 | 10 | 489 | 4 | Strong risk-on (90) | 11.41 | 6.74 | 2.85 | risk_above_5_percent:489 |
| S&P 500 | 2026-05-05 | 499 | 17 | 482 | 4 | Strong risk-on (90) | 10.63 | 6.21 | 2.86 | risk_above_5_percent:482 |
| S&P 500 | 2026-05-06 | 499 | 15 | 484 | 4 | Strong risk-on (90) | 10.74 | 6.16 | 2.96 | risk_above_5_percent:484 |
| S&P 500 | 2026-05-07 | 499 | 20 | 479 | 4 | Strong risk-on (90) | 10.86 | 6.20 | 2.93 | risk_above_5_percent:479 |
| S&P 500 | 2026-05-08 | 499 | 18 | 481 | 4 | Strong risk-on (90) | 10.86 | 6.30 | 2.90 | risk_above_5_percent:481 |
| S&P 500 | 2026-05-11 | 499 | 17 | 482 | 4 | Strong risk-on (90) | 10.88 | 6.19 | 2.94 | risk_above_5_percent:482 |
| S&P 500 | 2026-05-12 | 499 | 17 | 482 | 4 | Strong risk-on (90) | 10.80 | 6.14 | 2.92 | risk_above_5_percent:482 |
| S&P 500 | 2026-05-13 | 499 | 14 | 485 | 4 | Strong risk-on (90) | 10.87 | 6.38 | 2.94 | risk_above_5_percent:485 |
| S&P 500 | 2026-05-14 | 499 | 16 | 483 | 4 | Strong risk-on (90) | 10.62 | 6.20 | 2.92 | risk_above_5_percent:483 |
| S&P 500 | 2026-05-15 | 499 | 14 | 485 | 4 | Strong risk-on (90) | 10.77 | 6.27 | 2.90 | risk_above_5_percent:485 |
| S&P 500 | 2026-05-18 | 499 | 9 | 490 | 4 | Strong risk-on (90) | 10.70 | 6.20 | 2.90 | risk_above_5_percent:490 |
| S&P 500 | 2026-05-19 | 499 | 8 | 491 | 4 | Strong risk-on (90) | 10.85 | 6.35 | 2.90 | risk_above_5_percent:491 |
| S&P 500 | 2026-05-20 | 499 | 9 | 490 | 4 | Strong risk-on (90) | 11.01 | 6.35 | 2.90 | risk_above_5_percent:490 |
| S&P 500 | 2026-05-21 | 499 | 11 | 488 | 4 | Strong risk-on (90) | 10.96 | 6.29 | 2.93 | risk_above_5_percent:488 |
| S&P 500 | 2026-05-22 | 499 | 10 | 489 | 4 | Strong risk-on (90) | 10.96 | 6.28 | 2.88 | risk_above_5_percent:489 |
| S&P 500 | 2026-05-26 | 499 | 9 | 490 | 4 | Strong risk-on (90) | 10.87 | 6.19 | 2.85 | risk_above_5_percent:490 |
| S&P 500 | 2026-05-27 | 499 | 7 | 492 | 4 | Strong risk-on (90) | 10.75 | 6.13 | 2.86 | risk_above_5_percent:492 |
| S&P 500 | 2026-05-28 | 499 | 7 | 492 | 4 | Strong risk-on (90) | 10.68 | 6.17 | 2.85 | risk_above_5_percent:492 |
| S&P 500 | 2026-05-29 | 499 | 9 | 490 | 4 | Strong risk-on (90) | 10.69 | 6.15 | 2.83 | risk_above_5_percent:490 |
| S&P 500 | 2026-06-01 | 499 | 14 | 485 | 4 | Strong risk-on (90) | 10.79 | 6.23 | 2.85 | risk_above_5_percent:485 |
| S&P 500 | 2026-06-02 | 499 | 15 | 484 | 4 | Strong risk-on (90) | 10.77 | 6.26 | 2.86 | risk_above_5_percent:484 |
| S&P 500 | 2026-06-03 | 499 | 15 | 484 | 4 | Strong risk-on (90) | 10.67 | 6.24 | 2.85 | risk_above_5_percent:484 |
| S&P 500 | 2026-06-04 | 499 | 13 | 486 | 4 | Strong risk-on (90) | 10.69 | 6.28 | 2.89 | risk_above_5_percent:486 |
| S&P 500 | 2026-06-05 | 499 | 10 | 489 | 4 | Strong risk-on (90) | 10.74 | 6.28 | 2.88 | risk_above_5_percent:489 |
| S&P 500 | 2026-06-08 | 499 | 9 | 490 | 4 | Strong risk-on (90) | 10.54 | 6.17 | 2.85 | risk_above_5_percent:490 |
| S&P 500 | 2026-06-09 | 499 | 8 | 491 | 4 | Strong risk-on (90) | 10.81 | 6.39 | 2.88 | risk_above_5_percent:491 |
| S&P 500 | 2026-06-10 | 499 | 8 | 491 | 4 | Strong risk-on (90) | 10.88 | 6.45 | 2.89 | risk_above_5_percent:491 |
| S&P 500 | 2026-06-11 | 499 | 8 | 491 | 4 | Strong risk-on (90) | 11.05 | 6.51 | 2.93 | risk_above_5_percent:491 |
| S&P 500 | 2026-06-12 | 499 | 2 | 497 | 4 | Strong risk-on (90) | 10.93 | 6.55 | 2.93 | risk_above_5_percent:497 |
| S&P 500 | 2026-06-15 | 499 | 2 | 497 | 4 | Strong risk-on (90) | 11.02 | 6.64 | 2.91 | risk_above_5_percent:497 |
| S&P 500 | 2026-06-16 | 499 | 2 | 497 | 4 | Strong risk-on (90) | 11.03 | 6.70 | 2.88 | risk_above_5_percent:497 |
| S&P 500 | 2026-06-17 | 499 | 2 | 497 | 4 | Strong risk-on (90) | 11.18 | 6.68 | 2.92 | risk_above_5_percent:497 |
| S&P 500 | 2026-06-18 | 499 | 2 | 497 | 4 | Strong risk-on (90) | 11.13 | 6.61 | 2.94 | risk_above_5_percent:497 |
| S&P 500 | 2026-06-22 | 499 | 3 | 496 | 4 | Strong risk-on (90) | 10.96 | 6.37 | 2.98 | risk_above_5_percent:496 |
| S&P 500 | 2026-06-23 | 499 | 3 | 496 | 4 | Strong risk-on (90) | 10.74 | 6.20 | 2.96 | risk_above_5_percent:496 |
| S&P 500 | 2026-06-24 | 499 | 3 | 496 | 4 | Strong risk-on (90) | 10.80 | 6.34 | 2.99 | risk_above_5_percent:496 |
| S&P 500 | 2026-06-25 | 499 | 2 | 497 | 4 | Strong risk-on (90) | 11.19 | 6.77 | 3.02 | risk_above_5_percent:497 |
| S&P 500 | 2026-06-26 | 499 | 2 | 497 | 4 | Strong risk-on (90) | 11.37 | 6.87 | 3.01 | risk_above_5_percent:497 |
| S&P 500 | 2026-06-29 | 499 | 2 | 497 | 4 | Strong risk-on (90) | 11.63 | 7.15 | 2.99 | risk_above_5_percent:497 |
| S&P 500 | 2026-06-30 | 499 | 2 | 497 | 4 | Strong risk-on (90) | 11.62 | 7.07 | 2.97 | risk_above_5_percent:497 |
| S&P 500 | 2026-07-01 | 499 | 2 | 497 | 4 | Strong risk-on (90) | 11.70 | 6.97 | 3.00 | risk_above_5_percent:497 |
| S&P 500 | 2026-07-02 | 499 | 3 | 496 | 4 | Strong risk-on (90) | 11.56 | 6.90 | 3.06 | risk_above_5_percent:496 |
| S&P 500 | 2026-07-06 | 499 | 3 | 496 | 4 | Strong risk-on (90) | 11.49 | 6.95 | 3.06 | risk_above_5_percent:496 |
| S&P 500 | 2026-07-07 | 499 | 9 | 490 | 4 | Strong risk-on (90) | 11.67 | 7.07 | 3.06 | risk_above_5_percent:490 |
| S&P 500 | 2026-07-08 | 499 | 4 | 495 | 4 | Strong risk-on (90) | 11.56 | 6.99 | 3.06 | risk_above_5_percent:495 |
| S&P 500 | 2026-07-09 | 499 | 10 | 489 | 4 | Strong risk-on (90) | 11.47 | 6.93 | 3.04 | risk_above_5_percent:489 |
| S&P 500 | 2026-07-10 | 499 | 10 | 489 | 4 | Strong risk-on (90) | 11.40 | 6.90 | 2.97 | risk_above_5_percent:489 |
| S&P 500 | 2026-07-13 | 499 | 11 | 488 | 4 | Strong risk-on (90) | 11.10 | 6.68 | 2.93 | risk_above_5_percent:488 |
| S&P 500 | 2026-07-14 | 499 | 11 | 488 | 4 | Strong risk-on (90) | 10.96 | 6.57 | 2.93 | risk_above_5_percent:488 |
| S&P 500 | 2026-07-15 | 499 | 10 | 489 | 4 | Strong risk-on (90) | 11.10 | 6.58 | 2.94 | risk_above_5_percent:489 |
| S&P 500 | 2026-07-16 | 499 | 10 | 489 | 4 | Strong risk-on (90) | 11.31 | 6.77 | 2.98 | risk_above_5_percent:489 |
| S&P 500 | 2026-07-17 | 499 | 8 | 491 | 4 | Strong risk-on (90) | 11.51 | 7.02 | 3.01 | risk_above_5_percent:491 |
| S&P 500 | 2026-07-20 | 499 | 10 | 489 | 4 | Strong risk-on (90) | 11.32 | 6.93 | 2.98 | risk_above_5_percent:489 |
| S&P 500 | 2026-07-21 | 499 | 11 | 488 | 4 | Strong risk-on (90) | 11.08 | 6.69 | 3.00 | risk_above_5_percent:488 |
| S&P 500 | 2026-07-22 | 499 | 15 | 484 | 4 | Strong risk-on (90) | 10.66 | 6.19 | 2.96 | risk_above_5_percent:484 |
| S&P 500 | 2026-07-23 | 499 | 17 | 482 | 4 | Strong risk-on (90) | 10.67 | 6.12 | 3.02 | risk_above_5_percent:482 |

## Interpretation

The 5% gate is applied exactly as frozen and is mechanically functioning as documented. Whether the stop is operationally too wide is assessed from the reported decomposition: the entry-to-swing-low distance and the 1.5 ATR buffer are shown separately, so a wide stop cannot be misattributed to an arithmetic error.

The Demo 10 result measures a ten-name list and therefore cannot represent broad market availability. Comparing it with the larger configured snapshots separates universe-size scarcity from the strategy's natural selectivity. No threshold, strategy setting, universe membership, or production record was changed.

## Data and limitations

- Yahoo Finance adjusted daily OHLCV was loaded through the existing provider path; validated local Yahoo cache files were reused when current.
- Index memberships and sectors come from the timestamped local constituent snapshot.
- The All US Stocks universe is not replayed automatically because large scans require explicit user action; this audit retains the four-universe Milestone 39 scope.
- The completion-time estimate assumes future signal availability resembles this 60-session window and is not a profitability claim.
- Historical examples do not guarantee future signals or results.
- Production records changed: **NO**.
