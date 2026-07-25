# Trade Plan Variant Experiment

## Scope and method

This isolated experiment replays the existing cached calibration dataset. It does not change production scoring, factor weights, recommendation thresholds, or signal dates. Signals are generated after each daily candle closes and the same 15,780 historical signal candidates are supplied to every variant. The last chronological 30% (4,734 candidates) is out of sample.

All results include 5 bps adverse slippage per side, 5 bps transaction cost per side, 50% realised at TP1, the original stop retained for the remaining position, a maximum 30-session holding period, one concurrent position per ticker, and stop-first handling when a stop and target are touched in the same candle.

"Rejected trades" includes every out-of-sample candidate that could not be entered under that plan as well as overlapping same-ticker signals. The trade ledger records each exit leg and every rejection reason in [trade_plan_variant_trades.csv](/Users/beaudidier/Desktop/BEAU-AI-TRADER/artifacts/trade_plan_variant_trades.csv).

## Out-of-sample results

| Variant | Valid | Rejected | Win rate | Expectancy (R) | 95% CI | Profit factor | Average R | Max drawdown (R) | TP1 | TP2 | Stop | Avg. holding |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A — Next-open ATR | 363 | 4,371 | 44.08% | 0.1381 | -0.0103 to 0.2872 | 1.2401 | 0.1381 | -15.1636 | 42.42% | 25.62% | 61.71% | 13.02 days |
| B — Pullback | 42 | 4,692 | 54.76% | 0.5595 | 0.1409 to 0.9801 | 2.4233 | 0.5595 | -3.3237 | 42.86% | 28.57% | 33.33% | 21.52 days |
| C — Breakout | 442 | 4,292 | 37.10% | -0.0905 | -0.2135 to 0.0381 | 0.8626 | -0.0905 | -47.9436 | 36.88% | 22.17% | 71.49% | 8.76 days |

### Rejections

- A: 4,371 overlapping-position rejections.
- B: 2,308 limits not traded within three candles, 1,382 risk-above-5% rejections, and 1,002 overlapping-position rejections.
- C: 496 triggers not reached within three candles, 105 risk-above-5% rejections, and 3,691 overlapping-position rejections.

## Results by recommendation band

### WATCH (60–74)

| Variant | Valid | Rejected | Win rate | Expectancy (R) | 95% CI | Profit factor | Max drawdown (R) |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| A — Next-open ATR | 186 | 2,274 | 44.62% | 0.0977 | -0.0953 to 0.3000 | 1.1713 | -13.1080 |
| B — Pullback | 29 | 2,431 | 51.72% | 0.4679 | -0.0150 to 0.9580 | 2.1304 | -4.9539 |
| C — Breakout | 209 | 2,251 | 35.89% | -0.1353 | -0.3133 to 0.0512 | 0.7991 | -34.3803 |

### BUY (75–89)

| Variant | Valid | Rejected | Win rate | Expectancy (R) | 95% CI | Profit factor | Max drawdown (R) |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| A — Next-open ATR | 92 | 832 | 44.57% | 0.1634 | -0.1325 to 0.4573 | 1.2840 | -8.6992 |
| B — Pullback | 5 | 919 | 40.00% | 0.0514 | -0.9017 to 1.2166 | 1.1050 | -1.0324 |
| C — Breakout | 90 | 834 | 37.78% | -0.0209 | -0.3117 to 0.2773 | 0.9682 | -12.8477 |

## Results by market regime

| Variant | Regime | Valid | Rejected | Expectancy (R) | 95% CI | Profit factor | Max drawdown (R) |
| --- | --- | ---: | ---: | ---: | --- | ---: | ---: |
| A — Next-open ATR | Defensive | 101 | 1,039 | 0.3320 | 0.0570 to 0.6210 | 1.6514 | -6.5958 |
| A — Next-open ATR | Risk-on | 262 | 3,332 | 0.0634 | -0.1077 to 0.2380 | 1.1055 | -22.4175 |
| B — Pullback | Defensive | 10 | 1,130 | 0.2834 | -0.4350 to 1.0182 | 1.6887 | -4.1152 |
| B — Pullback | Risk-on | 32 | 3,562 | 0.6458 | 0.1515 to 1.1362 | 2.6672 | -3.3237 |
| C — Breakout | Defensive | 133 | 1,007 | -0.1827 | -0.4002 to 0.0386 | 0.7305 | -30.5371 |
| C — Breakout | Risk-on | 309 | 3,285 | -0.0509 | -0.2020 to 0.1016 | 0.9219 | -26.5694 |

## Decision

Recommend **Variant B — Pullback** for a future, separate validation experiment only. It is the sole variant satisfying the pre-defined gates: positive out-of-sample expectancy (0.5595R), profit factor above one (2.4233), at least 30 valid trades (42), and a fully positive bootstrap 95% expectancy interval (0.1409R to 0.9801R). Its interval is materially stronger than the current model's documented BUY point estimate of -0.0531R.

This is not a production-strategy change. The evidence is still preliminary: the overall Pullback sample is small, its BUY subset has only five trades and an interval spanning zero, and its result is sensitive to entry selectivity. Variant A is promising but does not qualify because its overall 95% interval crosses zero. Variant C does not qualify: expectancy is negative, profit factor is below one, and drawdown is substantially larger.

The machine-readable results are in [trade_plan_variant_results.json](/Users/beaudidier/Desktop/BEAU-AI-TRADER/artifacts/trade_plan_variant_results.json).
