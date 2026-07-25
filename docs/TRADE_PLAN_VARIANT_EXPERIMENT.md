# Trade Plan Variant Experiment

## Scope and method

The original 15,780 shared signal candidates and chronological 70/30 split were rerun without changing entries, stops, targets, costs, slippage, partial exits, or stop-first handling. Drawdown now uses actual partial and final exit dates rather than ticker iteration.

## Corrected out-of-sample results

| Variant | Trades | Rejected | Expectancy | Profit factor | Win rate | Old drawdown | Corrected drawdown | Max positions | Max open risk |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A — Next-open ATR | 363 | 4,371 | 0.1381R | 1.2401 | 44.08% | -15.1636R | -28.4875R | 30 | 28.5R |
| B — Pullback | 42 | 4,692 | 0.5595R | 2.4233 | 54.76% | -3.3237R | -3.9571R | 13 | 12.0R |
| C — Breakout | 442 | 4,292 | -0.0905R | 0.8626 | 37.10% | -47.9436R | -77.5874R | 30 | 27.0R |

## Recommendation

Variant B remains the only variant meeting the original experiment's expectancy gates, but its sample is only 42 trades and it reached 12R open risk. This remains a research result, not a production change. All variants remain paper-only pending separate portfolio-constrained validation.

Machine-readable results: [trade_plan_variant_results.json](/Users/beaudidier/Desktop/BEAU-AI-TRADER/artifacts/trade_plan_variant_results.json).
