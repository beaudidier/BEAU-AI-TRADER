# Calibration Decision

All values below are exact corrected out-of-sample values from `artifacts/ai_calibration_results.json`. The rerun uses 50% realized TP1 exits, the original stop on the remaining position, and per-fill slippage/costs. Scores are ordinal; they are not probabilities.

## Out-of-sample recommendation bands

| Band / verdict | Trades | Win rate | TP1 hit rate | TP2 hit rate | Stop-loss rate | Expectancy | Profit factor | Maximum drawdown | Average R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0–59 / SKIP | 72 | 52.78% | 36.11% | 29.17% | 41.67% | 0.5631R | 2.2401 | -5.2576R | 0.5631R |
| 60–74 / WATCH | 128 | 57.03% | 64.06% | 43.75% | 27.34% | -0.0415R | 0.8575 | -15.0853R | -0.0415R |
| 75–89 / BUY | 100 | 74.00% | 94.00% | 74.00% | 10.00% | 0.0122R | 1.1091 | -2.1934R | 0.0122R |
| 90–100 / STRONG BUY | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |

## What the correction changed

Compared with the previous full-position accounting, corrected average R changed from **0.1455R to 0.1215R** overall, **0.6346R to 0.5631R** for SKIP, **-0.0439R to -0.0415R** for WATCH, and **0.0359R to 0.0122R** for BUY. BUY win rate changed from **76.00% to 74.00%**. Every TP1 hit now records a separately realized TP1 leg; the remaining shares retain the original stop.

## Decision

Current thresholds should remain unchanged. The corrected run does not support a threshold change: BUY has better hit rates and lower drawdown than WATCH, but its expectancy is only 0.0122R, its profit factor is 1.1091, its bootstrap expectancy interval includes zero, and STRONG BUY has no samples.

No factor weight should change. The corrected results remain non-monotonic because SKIP has the largest observed average R. That outcome is insufficient to reweight factors or make SKIP actionable.

Conclusions not statistically justified:

- That BUY has a durable positive edge despite its near-zero corrected expectancy.
- That STRONG BUY is stronger than BUY.
- That any score is an empirical probability.
- That factor weights should be increased or decreased.
- That SKIP should be traded because it outperformed in this limited sample.
