# AI Decision Engine Calibration Audit

## Executive verdict

The current system has **not demonstrated predictive value** in this audit run. The audit runner requested rolling three-year daily histories for 30 liquid US stocks, but the Yahoo development provider returned insufficient history for all 30 symbols during the run. Therefore, there are zero calibration and zero out-of-sample trades. No confidence score should be interpreted as a probability, and the present thresholds and weights are not empirically justified.

## Method

- Universe: 30 liquid US stocks across technology, consumer, financials, health care, energy, industrials, staples, utilities, real estate, communication services, and materials.
- Data: Yahoo Finance daily history, rolling three-year request.
- Split: chronological 70% calibration / 30% out-of-sample by signal date; no random shuffling.
- Signal: analysis uses only candles through the signal close. Entry uses the following candle's open.
- Execution: 5 bps slippage and 5 bps transaction cost per side; one open trade per ticker; 30-day maximum holding window.
- Intrabar ambiguity: when stop and a target occur in one candle, the stop is assumed first.
- Results: [ai_calibration_results.json](../artifacts/ai_calibration_results.json) and [ai_calibration_trades.csv](../artifacts/ai_calibration_trades.csv).

## Out-of-sample results

No out-of-sample trades were generated because all 30 provider requests were recorded as missing or insufficient. All displayed zeroes in the artifact mean “not measured”, not zero performance.

## Results per confidence band

| Band | Signals | Trades | Conclusion |
| --- | ---: | ---: | --- |
| 0–59 | 0 | 0 | Insufficient sample |
| 60–74 | 0 | 0 | Insufficient sample |
| 75–89 | 0 | 0 | Insufficient sample |
| 90–100 | 0 | 0 | Insufficient sample |

TP rates, stop rates, win rate, return, R multiple, expectancy, profit factor, drawdown, holding time, MFE, and MAE are consequently unmeasured.

## Factor usefulness

Trend, momentum, volume, support/resistance, volatility, relative strength, market regime, ticker, and sector analysis could not be estimated. A factor must have materially sized out-of-sample samples before it can be called useful or discarded.

## Bias and leakage findings

- Look-ahead: the runner slices each symbol and benchmark at the signal close; the trade enters next open.
- Same-candle ambiguity: conservatively resolved in favor of the stop.
- Duplicate/overlap: one active trade per ticker is enforced.
- Unrealistic fills: explicit slippage and transaction costs are applied.
- Data leakage: no future values are passed into the analysis call.
- Survivorship bias: present. The fixed liquid-current-ticker universe is not a historical constituent universe.
- Provider failures: material and blocking in this run; all failures are retained in the JSON artifact.
- Probability language: a score is a ranking/model score, not a calibrated probability. The product must not state that a score of 70 means a 70% chance of success.

## Are current thresholds justified?

No. The 0–59, 60–74, 75–89, and 90–100 thresholds were not changed, but this run supplies no evidence to validate them. The current architecture also permits WATCH signals to be measured; whether they should be tradeable is a separate policy question.

## Recommended changes (not implemented)

1. Re-run with a reliable, versioned historical-data snapshot and preserve raw input data alongside the audit artifacts.
2. Use historical index membership to reduce survivorship bias.
3. Require minimum out-of-sample sample sizes and confidence intervals before changing thresholds or weights.
4. Compare each band against a simple buy-and-hold and random-entry baseline after reliable data is available.
5. Calibrate language only after empirical hit rates are stable across regimes and sectors.

## Limitations

This is a preliminary engineering audit, not investment research. The Yahoo provider is development-only and the failed data run prevents any claim about accuracy, expectancy, or factor usefulness. Results will change with data quality, costs, market regime, ticker membership, and execution assumptions.
