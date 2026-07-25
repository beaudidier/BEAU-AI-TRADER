# AI Decision Engine Calibration Audit

## Executive verdict

The reliable-data rerun completed with 30/30 validated liquid US symbols and SPY. The current score bands show **some ranking evidence in hit rates**: the 75–89 band reached TP1 93.94% of the time versus 64.29% for 60–74. However, returns and R multiples are not monotonic across bands, the 90–100 band produced zero out-of-sample observations, and the fixed current-ticker universe has survivorship bias. The score is not a probability and should not be presented as one.

## Dataset and execution controls

- Explicit range: 2023-07-16 through 2026-07-25 (end exclusive), daily OHLCV from Yahoo Finance.
- Validation: every symbol and SPY had at least 600 valid candles (the cached dataset has 759), required OHLCV columns, chronological unique dates, positive numeric values, and a latest date before the exclusive end date.
- Reliability: three individual download attempts per symbol, exact failures retained, CSV cache in `artifacts/calibration_dataset/`, and no audit unless at least 25 of 30 symbols validate. This run had no provider failures.
- Split: chronological 70% calibration / 30% out-of-sample by signal date; never shuffled.
- Signal/execution: indicators use only information available at the signal close; entry is the next daily open. One active trade per ticker is allowed. A simultaneous stop/target candle resolves to the stop first. Signals without a complete 30-session forward window are excluded. The simulation includes 5 bps slippage and 5 bps transaction cost on each side and a 30-day maximum hold.

Artifacts: [results JSON](../artifacts/ai_calibration_results.json) and [trade CSV](../artifacts/ai_calibration_trades.csv).

## Out-of-sample results

316 OOS trades were generated. TP1 hit rate was 67.41%, TP2 hit rate 48.10%, stop-loss rate 21.52%, win rate 62.03%, average return 0.6679%, average R 0.1853, profit factor 1.6597, maximum drawdown -15.2058R, and average holding time 15.13 days. These are simulation results under the stated rules, not a live-trading claim.

## Results per confidence band

| Band | Trades | TP1 | TP2 | Stop | Win rate | Avg R | Profit factor |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0–59 | 77 | 38.96% | 29.87% | 37.66% | 54.55% | 0.7117 | 2.6625 |
| 60–74 (WATCH) | 140 | 64.29% | 42.86% | 21.43% | 58.57% | 0.0015 | 1.0052 |
| 75–89 (BUY) | 99 | 93.94% | 69.70% | 9.09% | 72.73% | 0.0357 | 1.2198 |
| 90–100 (STRONG BUY) | 0 | — | — | — | — | — | — |

BUY clearly outperformed WATCH on TP1, TP2, stop-loss rate, and win rate. It only modestly outperformed WATCH on average R, and neither comparison validates the score as a probability. The 0–59 band’s unusually high average R conflicts with the hit-rate ordering; that is a warning that the present exit/risk construction and small cross-sectional sample need deeper review.

## Factor and regime usefulness

The JSON artifact contains OOS performance grouped by every raw trend, momentum, volume, support/resistance, volatility, and relative-strength score, plus regime, ticker, and sector. At a high level, Risk-on observations (247 trades) had a 70.04% TP1 rate and 0.0915 average R; Defensive observations (69 trades) had a 57.97% TP1 rate and 0.5208 average R. These groups are not large enough to justify changing weights.

## Bias and leakage audit

- No look-ahead: history is sliced through the signal close; execution begins next open.
- Same-candle ambiguity: stop first, conservatively.
- Duplicate/overlap control: one open trade per ticker.
- Fill realism: fixed explicit costs and slippage are included; liquidity, spread variation, and gaps are not fully modeled.
- Data leakage: no future OHLCV is passed to indicator/plan construction.
- Survivorship bias remains: the 30 symbols are a current liquid universe, not historical index constituents.
- Incomplete latest candle: rejected by dataset validation.
- Probability language remains uncalibrated: a score of 70 is not 70% probability.

## Are thresholds justified?

Not yet. The BUY threshold has better OOS hit-rate evidence than WATCH in this sample, but there are no STRONG BUY observations, returns are not monotonic, and no confidence intervals or external baseline were calculated. No thresholds, weights, or decision logic were changed.

## Remaining limitations and recommended next steps

1. Preserve/version the cached raw dataset before treating results as a baseline.
2. Add historical universe membership to address survivorship bias.
3. Add confidence intervals, benchmark returns, and larger multi-regime samples before calibration changes.
4. Investigate why the low-score band has high realized R despite worse target/stop hit rates.
5. Keep score language ordinal until robust calibration demonstrates stable empirical probabilities.
