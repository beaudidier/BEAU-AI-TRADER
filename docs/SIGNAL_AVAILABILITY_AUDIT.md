# Signal Availability Audit

## Executive verdict

The frozen Regime-Gated Pullback strategy was replayed through the registered production strategy interface for each of the most recent **60** completed US sessions (2026-04-28 through 2026-07-23).

| Configured universe | Names | Valid signals | Signals/day | Zero-signal days | Valid/week | Estimated weeks to 100 completed |
|---|---:|---:|---:|---:|---:|---:|
| Demo 10 | 10 | 1 | 0.017 | 59 (98.33%) | 0.083 | n/a |
| Dow 30 | 30 | 77 | 1.283 | 24 (40.00%) | 6.417 | 26.0 |
| Nasdaq 100 | 30 | 106 | 1.767 | 24 (40.00%) | 8.833 | 21.9 |
| S&P 500 | 51 | 114 | 1.900 | 23 (38.33%) | 9.500 | 18.3 |

The estimate to 100 completed trades uses the observed completion rate only for signals with enough later candles for the full entry and holding window. It is an availability estimate, not a performance forecast.

The production universe labels are historical local snapshots: the configured S&P 500 contains **51** names and the configured Nasdaq 100 contains **30**. This audit intentionally preserved those exact memberships. The labels must not be interpreted as complete current index membership.

## Direct findings

- Stop formula arithmetic bug: **NO**
- Stop geometry structurally wide relative to the 5% cap in this window: **YES**. In the largest configured snapshot (S&P 500), 2946 of 3060 completed scans breached the 5% cap. The median rejected risk was 11.02%, decomposed into a 6.67% entry-to-swing-low distance and a 4.19% ATR buffer. The stop formula is therefore structurally wide relative to the frozen cap in this window, but it is not being calculated incorrectly.
- Demo universe too small for practical signal availability: **YES**
- 5% rule functioning as implemented: **YES**
- Frozen strategy naturally selective in this window: **YES**
- Volatility dependence: The risk gate rejected 100% of high-ATR observations in every configured universe; low-ATR observations had materially lower rejection rates in the larger snapshots.
- Regime dependence: Not identifiable from this 60-session sample because every audited session was classified Strong risk-on.

## Calculation integrity

- Production/standalone mismatches: **0**
- Risk observations checked: **4260**
- Maximum formula error: **0.0000056791 percentage points**
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
- Valid signals: **77**
- Rejected setups: **1723**
- Provider failures: **0**
- Signals per trading day: **1.2833**
- Zero-signal frequency: **40.00%**
- Average valid signals per week: **6.4167**
- Mature signals used for outcome estimate: **45**
- Mature signal completion rate: **60.00%**
- Estimated weeks to issue 100 signals: **15.6**
- Estimated weeks to 100 completed trades: **26.0**
- Rejection reasons: `risk_above_5_percent` 1723

5% risk-limit distribution:

- Total risk-limit rejections: **1723**
- Only slightly above 5% (greater than 5% through 7.5%): **373**
- Above 7.5%: **1350**
- Above 10%: **843**
- Median rejected risk: **9.94%**
- Median entry-to-swing-low distance: **5.88%**
- Median 1.5 ATR buffer: **3.87%**
- Largest rejection sector: **Technology** (22.34%)
- One-sector dominance (>50%): **NO**

Risk-limit rejection rate by volatility:

| ATR bucket | Completed scans | Risk rejections | Rate |
|---|---:|---:|---:|
| High (>4% ATR) | 178 | 178 | 100.00% |
| Low (<2% ATR) | 278 | 202 | 72.66% |
| Moderate (2-4% ATR) | 1344 | 1343 | 99.93% |

Risk-limit rejection rate by market regime:

| Regime | Completed scans | Risk rejections | Rate |
|---|---:|---:|---:|
| Strong risk-on | 1800 | 1723 | 95.72% |

### Nasdaq 100

- Configured names: **30**
- Completed symbol/date scans: **1800**
- Valid signals: **106**
- Rejected setups: **1694**
- Provider failures: **0**
- Signals per trading day: **1.7667**
- Zero-signal frequency: **40.00%**
- Average valid signals per week: **8.8333**
- Mature signals used for outcome estimate: **58**
- Mature signal completion rate: **51.72%**
- Estimated weeks to issue 100 signals: **11.3**
- Estimated weeks to 100 completed trades: **21.9**
- Rejection reasons: `risk_above_5_percent` 1694

5% risk-limit distribution:

- Total risk-limit rejections: **1694**
- Only slightly above 5% (greater than 5% through 7.5%): **191**
- Above 7.5%: **1503**
- Above 10%: **1207**
- Median rejected risk: **12.44%**
- Median entry-to-swing-low distance: **7.30%**
- Median 1.5 ATR buffer: **4.90%**
- Largest rejection sector: **Technology** (43.98%)
- One-sector dominance (>50%): **NO**

Risk-limit rejection rate by volatility:

| ATR bucket | Completed scans | Risk rejections | Rate |
|---|---:|---:|---:|
| High (>4% ATR) | 509 | 509 | 100.00% |
| Low (<2% ATR) | 205 | 100 | 48.78% |
| Moderate (2-4% ATR) | 1086 | 1085 | 99.91% |

Risk-limit rejection rate by market regime:

| Regime | Completed scans | Risk rejections | Rate |
|---|---:|---:|---:|
| Strong risk-on | 1800 | 1694 | 94.11% |

### S&P 500

- Configured names: **51**
- Completed symbol/date scans: **3060**
- Valid signals: **114**
- Rejected setups: **2946**
- Provider failures: **0**
- Signals per trading day: **1.9000**
- Zero-signal frequency: **38.33%**
- Average valid signals per week: **9.5000**
- Mature signals used for outcome estimate: **66**
- Mature signal completion rate: **57.58%**
- Estimated weeks to issue 100 signals: **10.5**
- Estimated weeks to 100 completed trades: **18.3**
- Rejection reasons: `risk_above_5_percent` 2946

5% risk-limit distribution:

- Total risk-limit rejections: **2946**
- Only slightly above 5% (greater than 5% through 7.5%): **489**
- Above 7.5%: **2457**
- Above 10%: **1756**
- Median rejected risk: **11.02%**
- Median entry-to-swing-low distance: **6.67%**
- Median 1.5 ATR buffer: **4.19%**
- Largest rejection sector: **Technology** (29.36%)
- One-sector dominance (>50%): **NO**

Risk-limit rejection rate by volatility:

| ATR bucket | Completed scans | Risk rejections | Rate |
|---|---:|---:|---:|
| High (>4% ATR) | 638 | 638 | 100.00% |
| Low (<2% ATR) | 382 | 271 | 70.94% |
| Moderate (2-4% ATR) | 2040 | 2037 | 99.85% |

Risk-limit rejection rate by market regime:

| Regime | Completed scans | Risk rejections | Rate |
|---|---:|---:|---:|
| Strong risk-on | 3060 | 2946 | 96.27% |

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
| Dow 30 | 2026-04-28 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 10.83 | 7.45 | 2.48 | risk_above_5_percent:28 |
| Dow 30 | 2026-04-29 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 10.59 | 6.64 | 2.50 | risk_above_5_percent:28 |
| Dow 30 | 2026-04-30 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 10.49 | 6.74 | 2.54 | risk_above_5_percent:28 |
| Dow 30 | 2026-05-01 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 10.12 | 6.43 | 2.56 | risk_above_5_percent:28 |
| Dow 30 | 2026-05-04 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 10.00 | 6.37 | 2.54 | risk_above_5_percent:28 |
| Dow 30 | 2026-05-05 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 9.18 | 5.59 | 2.54 | risk_above_5_percent:27 |
| Dow 30 | 2026-05-06 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 9.39 | 5.60 | 2.54 | risk_above_5_percent:27 |
| Dow 30 | 2026-05-07 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 9.26 | 5.46 | 2.53 | risk_above_5_percent:27 |
| Dow 30 | 2026-05-08 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 9.24 | 5.47 | 2.50 | risk_above_5_percent:28 |
| Dow 30 | 2026-05-11 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 9.15 | 5.20 | 2.51 | risk_above_5_percent:28 |
| Dow 30 | 2026-05-12 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 8.65 | 4.90 | 2.50 | risk_above_5_percent:28 |
| Dow 30 | 2026-05-13 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 8.69 | 5.32 | 2.47 | risk_above_5_percent:28 |
| Dow 30 | 2026-05-14 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 8.44 | 5.01 | 2.38 | risk_above_5_percent:28 |
| Dow 30 | 2026-05-15 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 8.20 | 4.92 | 2.41 | risk_above_5_percent:28 |
| Dow 30 | 2026-05-18 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 8.33 | 4.93 | 2.45 | risk_above_5_percent:30 |
| Dow 30 | 2026-05-19 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 8.30 | 5.04 | 2.44 | risk_above_5_percent:30 |
| Dow 30 | 2026-05-20 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 8.17 | 5.02 | 2.50 | risk_above_5_percent:30 |
| Dow 30 | 2026-05-21 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 8.89 | 5.17 | 2.51 | risk_above_5_percent:30 |
| Dow 30 | 2026-05-22 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 9.32 | 5.55 | 2.50 | risk_above_5_percent:30 |
| Dow 30 | 2026-05-26 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 9.27 | 5.43 | 2.56 | risk_above_5_percent:29 |
| Dow 30 | 2026-05-27 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 9.23 | 5.14 | 2.50 | risk_above_5_percent:30 |
| Dow 30 | 2026-05-28 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 8.79 | 4.99 | 2.47 | risk_above_5_percent:30 |
| Dow 30 | 2026-05-29 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 8.63 | 4.96 | 2.48 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-01 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 8.66 | 4.95 | 2.48 | risk_above_5_percent:27 |
| Dow 30 | 2026-06-02 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 8.73 | 4.80 | 2.44 | risk_above_5_percent:27 |
| Dow 30 | 2026-06-03 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 9.38 | 5.32 | 2.51 | risk_above_5_percent:27 |
| Dow 30 | 2026-06-04 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 8.99 | 5.01 | 2.62 | risk_above_5_percent:28 |
| Dow 30 | 2026-06-05 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 9.15 | 4.94 | 2.58 | risk_above_5_percent:28 |
| Dow 30 | 2026-06-08 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 9.16 | 4.99 | 2.56 | risk_above_5_percent:28 |
| Dow 30 | 2026-06-09 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 9.12 | 5.09 | 2.59 | risk_above_5_percent:28 |
| Dow 30 | 2026-06-10 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 9.36 | 5.19 | 2.56 | risk_above_5_percent:28 |
| Dow 30 | 2026-06-11 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 9.63 | 5.34 | 2.62 | risk_above_5_percent:28 |
| Dow 30 | 2026-06-12 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 9.89 | 5.42 | 2.55 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-15 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 9.96 | 5.68 | 2.59 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-16 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 9.91 | 5.77 | 2.55 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-17 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 10.02 | 5.96 | 2.62 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-18 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 9.91 | 5.90 | 2.67 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-22 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 9.70 | 5.87 | 2.64 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-23 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 9.70 | 5.97 | 2.59 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-24 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 10.11 | 6.04 | 2.59 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-25 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 10.64 | 6.65 | 2.72 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-26 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 10.85 | 6.93 | 2.72 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-29 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 10.98 | 7.13 | 2.66 | risk_above_5_percent:30 |
| Dow 30 | 2026-06-30 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 11.53 | 7.06 | 2.61 | risk_above_5_percent:30 |
| Dow 30 | 2026-07-01 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 11.83 | 7.00 | 2.61 | risk_above_5_percent:30 |
| Dow 30 | 2026-07-02 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 11.14 | 6.66 | 2.64 | risk_above_5_percent:30 |
| Dow 30 | 2026-07-06 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 11.00 | 6.58 | 2.64 | risk_above_5_percent:30 |
| Dow 30 | 2026-07-07 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 11.25 | 6.85 | 2.71 | risk_above_5_percent:28 |
| Dow 30 | 2026-07-08 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 11.34 | 6.68 | 2.77 | risk_above_5_percent:30 |
| Dow 30 | 2026-07-09 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 10.96 | 6.49 | 2.72 | risk_above_5_percent:28 |
| Dow 30 | 2026-07-10 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 10.41 | 6.52 | 2.64 | risk_above_5_percent:28 |
| Dow 30 | 2026-07-13 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 10.22 | 6.31 | 2.65 | risk_above_5_percent:28 |
| Dow 30 | 2026-07-14 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 9.89 | 5.44 | 2.57 | risk_above_5_percent:28 |
| Dow 30 | 2026-07-15 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 10.05 | 5.93 | 2.58 | risk_above_5_percent:28 |
| Dow 30 | 2026-07-16 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 10.31 | 6.33 | 2.64 | risk_above_5_percent:28 |
| Dow 30 | 2026-07-17 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 10.61 | 6.46 | 2.72 | risk_above_5_percent:28 |
| Dow 30 | 2026-07-20 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 10.14 | 6.31 | 2.73 | risk_above_5_percent:28 |
| Dow 30 | 2026-07-21 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 10.11 | 6.15 | 2.68 | risk_above_5_percent:28 |
| Dow 30 | 2026-07-22 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 9.46 | 5.44 | 2.60 | risk_above_5_percent:28 |
| Dow 30 | 2026-07-23 | 30 | 2 | 28 | 0 | Strong risk-on (90) | 9.60 | 5.65 | 2.70 | risk_above_5_percent:28 |
| Nasdaq 100 | 2026-04-28 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 14.57 | 10.34 | 2.92 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-04-29 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 14.53 | 10.26 | 2.90 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-04-30 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 14.83 | 10.67 | 3.12 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-05-01 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 13.99 | 9.21 | 3.11 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-05-04 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 13.54 | 8.88 | 3.05 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-05-05 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 11.70 | 7.08 | 3.03 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-05-06 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 11.76 | 7.08 | 2.95 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-05-07 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 11.34 | 6.80 | 2.87 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-05-08 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 12.29 | 7.24 | 2.77 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-05-11 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 11.38 | 6.64 | 2.75 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-05-12 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 10.83 | 6.12 | 2.80 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-05-13 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 10.67 | 6.33 | 2.83 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-05-14 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 10.40 | 6.20 | 2.81 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-05-15 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 10.48 | 6.48 | 2.82 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-05-18 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 10.69 | 6.39 | 2.87 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-05-19 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 10.83 | 6.39 | 2.86 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-05-20 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 10.75 | 6.20 | 2.83 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-05-21 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 10.80 | 6.03 | 2.81 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-05-22 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 10.67 | 5.85 | 2.74 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-05-26 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 10.78 | 5.92 | 2.67 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-05-27 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 9.87 | 5.36 | 2.64 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-05-28 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 8.65 | 4.80 | 2.64 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-05-29 | 30 | 1 | 29 | 0 | Strong risk-on (90) | 9.89 | 5.58 | 2.62 | risk_above_5_percent:29 |
| Nasdaq 100 | 2026-06-01 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 10.63 | 6.82 | 2.69 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-06-02 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 10.71 | 6.53 | 2.65 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-06-03 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 10.80 | 6.61 | 2.81 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-06-04 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 10.64 | 6.33 | 2.92 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-06-05 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 10.59 | 6.17 | 2.98 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-06-08 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 10.36 | 5.88 | 2.93 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-06-09 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 10.65 | 6.49 | 2.92 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-06-10 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 10.96 | 6.50 | 2.94 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-06-11 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 11.64 | 6.72 | 3.05 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-06-12 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 11.38 | 6.59 | 3.02 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-06-15 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 11.54 | 6.80 | 3.14 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-06-16 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 11.24 | 7.03 | 3.04 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-06-17 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 11.62 | 6.84 | 3.08 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-06-18 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 11.51 | 6.67 | 3.10 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-06-22 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 11.59 | 6.64 | 3.22 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-06-23 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 11.24 | 6.53 | 3.17 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-06-24 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 11.20 | 6.64 | 3.21 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-06-25 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 12.55 | 7.18 | 3.21 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-06-26 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 12.74 | 7.38 | 3.29 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-06-29 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 12.86 | 7.71 | 3.53 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-06-30 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 13.17 | 7.93 | 3.42 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-07-01 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 12.97 | 7.78 | 3.47 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-07-02 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 12.94 | 7.92 | 3.46 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-07-06 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 13.03 | 7.86 | 3.38 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-07-07 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 13.05 | 7.84 | 3.38 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-07-08 | 30 | 0 | 30 | 0 | Strong risk-on (90) | 12.91 | 7.90 | 3.40 | risk_above_5_percent:30 |
| Nasdaq 100 | 2026-07-09 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 13.10 | 7.99 | 3.39 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-07-10 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 13.12 | 8.16 | 3.38 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-07-13 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 13.04 | 7.71 | 3.36 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-07-14 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 12.37 | 7.32 | 3.35 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-07-15 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 12.78 | 7.64 | 3.39 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-07-16 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 13.01 | 7.62 | 3.35 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-07-17 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 13.50 | 7.74 | 3.49 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-07-20 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 13.20 | 7.58 | 3.42 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-07-21 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 12.88 | 7.35 | 3.31 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-07-22 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 12.88 | 7.41 | 3.28 | risk_above_5_percent:27 |
| Nasdaq 100 | 2026-07-23 | 30 | 3 | 27 | 0 | Strong risk-on (90) | 14.37 | 7.89 | 3.52 | risk_above_5_percent:27 |
| S&P 500 | 2026-04-28 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 11.28 | 7.33 | 2.64 | risk_above_5_percent:48 |
| S&P 500 | 2026-04-29 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 11.03 | 6.99 | 2.69 | risk_above_5_percent:48 |
| S&P 500 | 2026-04-30 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 11.49 | 7.19 | 2.88 | risk_above_5_percent:48 |
| S&P 500 | 2026-05-01 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 11.45 | 6.95 | 2.81 | risk_above_5_percent:48 |
| S&P 500 | 2026-05-04 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 11.54 | 6.84 | 2.78 | risk_above_5_percent:48 |
| S&P 500 | 2026-05-05 | 51 | 4 | 47 | 0 | Strong risk-on (90) | 11.14 | 6.82 | 2.74 | risk_above_5_percent:47 |
| S&P 500 | 2026-05-06 | 51 | 4 | 47 | 0 | Strong risk-on (90) | 10.74 | 6.57 | 2.73 | risk_above_5_percent:47 |
| S&P 500 | 2026-05-07 | 51 | 5 | 46 | 0 | Strong risk-on (90) | 10.42 | 6.21 | 2.70 | risk_above_5_percent:46 |
| S&P 500 | 2026-05-08 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 10.35 | 6.29 | 2.61 | risk_above_5_percent:48 |
| S&P 500 | 2026-05-11 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 10.73 | 6.34 | 2.65 | risk_above_5_percent:48 |
| S&P 500 | 2026-05-12 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 10.40 | 5.77 | 2.63 | risk_above_5_percent:48 |
| S&P 500 | 2026-05-13 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 10.92 | 6.21 | 2.63 | risk_above_5_percent:48 |
| S&P 500 | 2026-05-14 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 10.44 | 6.20 | 2.62 | risk_above_5_percent:48 |
| S&P 500 | 2026-05-15 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 10.23 | 6.29 | 2.63 | risk_above_5_percent:48 |
| S&P 500 | 2026-05-18 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 10.26 | 6.10 | 2.65 | risk_above_5_percent:51 |
| S&P 500 | 2026-05-19 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 10.64 | 6.27 | 2.65 | risk_above_5_percent:51 |
| S&P 500 | 2026-05-20 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 10.66 | 6.33 | 2.73 | risk_above_5_percent:51 |
| S&P 500 | 2026-05-21 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 10.58 | 6.27 | 2.70 | risk_above_5_percent:51 |
| S&P 500 | 2026-05-22 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 10.67 | 6.12 | 2.61 | risk_above_5_percent:51 |
| S&P 500 | 2026-05-26 | 51 | 1 | 50 | 0 | Strong risk-on (90) | 10.40 | 5.96 | 2.64 | risk_above_5_percent:50 |
| S&P 500 | 2026-05-27 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 10.58 | 6.04 | 2.61 | risk_above_5_percent:51 |
| S&P 500 | 2026-05-28 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 10.04 | 5.65 | 2.61 | risk_above_5_percent:51 |
| S&P 500 | 2026-05-29 | 51 | 1 | 50 | 0 | Strong risk-on (90) | 9.90 | 5.55 | 2.56 | risk_above_5_percent:50 |
| S&P 500 | 2026-06-01 | 51 | 4 | 47 | 0 | Strong risk-on (90) | 10.06 | 5.57 | 2.61 | risk_above_5_percent:47 |
| S&P 500 | 2026-06-02 | 51 | 4 | 47 | 0 | Strong risk-on (90) | 10.27 | 5.81 | 2.61 | risk_above_5_percent:47 |
| S&P 500 | 2026-06-03 | 51 | 4 | 47 | 0 | Strong risk-on (90) | 9.87 | 6.44 | 2.68 | risk_above_5_percent:47 |
| S&P 500 | 2026-06-04 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 10.06 | 5.94 | 2.70 | risk_above_5_percent:48 |
| S&P 500 | 2026-06-05 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 10.21 | 5.72 | 2.70 | risk_above_5_percent:48 |
| S&P 500 | 2026-06-08 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 10.28 | 5.67 | 2.74 | risk_above_5_percent:48 |
| S&P 500 | 2026-06-09 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 10.07 | 6.09 | 2.73 | risk_above_5_percent:48 |
| S&P 500 | 2026-06-10 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 10.39 | 6.10 | 2.80 | risk_above_5_percent:48 |
| S&P 500 | 2026-06-11 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 10.66 | 5.86 | 2.82 | risk_above_5_percent:48 |
| S&P 500 | 2026-06-12 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 10.68 | 6.16 | 2.79 | risk_above_5_percent:51 |
| S&P 500 | 2026-06-15 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 10.63 | 6.23 | 2.76 | risk_above_5_percent:51 |
| S&P 500 | 2026-06-16 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 10.83 | 6.49 | 2.73 | risk_above_5_percent:51 |
| S&P 500 | 2026-06-17 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 10.69 | 6.33 | 2.76 | risk_above_5_percent:51 |
| S&P 500 | 2026-06-18 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 10.28 | 6.36 | 2.70 | risk_above_5_percent:51 |
| S&P 500 | 2026-06-22 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 9.81 | 5.88 | 2.78 | risk_above_5_percent:51 |
| S&P 500 | 2026-06-23 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 9.94 | 5.95 | 2.81 | risk_above_5_percent:51 |
| S&P 500 | 2026-06-24 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 10.01 | 6.09 | 2.86 | risk_above_5_percent:51 |
| S&P 500 | 2026-06-25 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 10.69 | 6.77 | 2.90 | risk_above_5_percent:51 |
| S&P 500 | 2026-06-26 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 11.09 | 6.83 | 2.90 | risk_above_5_percent:51 |
| S&P 500 | 2026-06-29 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 11.29 | 7.05 | 2.87 | risk_above_5_percent:51 |
| S&P 500 | 2026-06-30 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 11.63 | 7.09 | 2.83 | risk_above_5_percent:51 |
| S&P 500 | 2026-07-01 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 12.01 | 7.37 | 2.82 | risk_above_5_percent:51 |
| S&P 500 | 2026-07-02 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 11.23 | 6.84 | 2.83 | risk_above_5_percent:51 |
| S&P 500 | 2026-07-06 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 11.45 | 7.05 | 2.91 | risk_above_5_percent:51 |
| S&P 500 | 2026-07-07 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 11.79 | 7.15 | 2.82 | risk_above_5_percent:48 |
| S&P 500 | 2026-07-08 | 51 | 0 | 51 | 0 | Strong risk-on (90) | 11.89 | 7.27 | 2.85 | risk_above_5_percent:51 |
| S&P 500 | 2026-07-09 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 12.11 | 7.30 | 2.81 | risk_above_5_percent:48 |
| S&P 500 | 2026-07-10 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 12.13 | 7.30 | 2.76 | risk_above_5_percent:48 |
| S&P 500 | 2026-07-13 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 11.86 | 6.69 | 2.70 | risk_above_5_percent:48 |
| S&P 500 | 2026-07-14 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 11.47 | 6.70 | 2.73 | risk_above_5_percent:48 |
| S&P 500 | 2026-07-15 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 12.35 | 6.84 | 2.72 | risk_above_5_percent:48 |
| S&P 500 | 2026-07-16 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 12.60 | 7.28 | 2.91 | risk_above_5_percent:48 |
| S&P 500 | 2026-07-17 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 12.76 | 7.68 | 2.95 | risk_above_5_percent:48 |
| S&P 500 | 2026-07-20 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 12.60 | 7.57 | 2.98 | risk_above_5_percent:48 |
| S&P 500 | 2026-07-21 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 11.88 | 7.02 | 3.00 | risk_above_5_percent:48 |
| S&P 500 | 2026-07-22 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 11.38 | 6.86 | 2.93 | risk_above_5_percent:48 |
| S&P 500 | 2026-07-23 | 51 | 3 | 48 | 0 | Strong risk-on (90) | 11.07 | 7.34 | 3.04 | risk_above_5_percent:48 |

## Interpretation

The 5% gate is applied exactly as frozen and is mechanically functioning as documented. Whether the stop is operationally too wide is assessed from the reported decomposition: the entry-to-swing-low distance and the 1.5 ATR buffer are shown separately, so a wide stop cannot be misattributed to an arithmetic error.

The Demo 10 result measures a ten-name list and therefore cannot represent broad market availability. Comparing it with the larger configured snapshots separates universe-size scarcity from the strategy's natural selectivity. No threshold, strategy setting, universe membership, or production record was changed.

## Data and limitations

- Yahoo Finance adjusted daily OHLCV was loaded through the existing provider path; validated local Yahoo cache files were reused when current.
- Current configured index snapshots are incomplete versus their labels; conclusions apply only to the exact symbols listed in the artifact.
- Sector labels come from the repository's frozen multi-sector research universe, supplemented only for configured symbols absent from that map.
- The completion-time estimate assumes future signal availability resembles this 60-session window and is not a profitability claim.
- Historical examples do not guarantee future signals or results.
- Production records changed: **NO**.
