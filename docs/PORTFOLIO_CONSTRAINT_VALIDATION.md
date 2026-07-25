# Portfolio Constraint Validation

## Executive verdict

**160 of 256** tested combinations pass every predeclared approval criterion.

The best risk-adjusted configuration is **10 positions, 10R open risk, 1R daily new risk, ranked by highest confidence**. It produces 0.4275R expectancy and -12.4900R maximum drawdown.

The lowest-drawdown viable configuration is **10 positions, 5R open risk, 5R daily new risk, ranked by best risk reward**, with -9.1302R drawdown and 0.3325R expectancy.

No production limits were implemented.

## Baseline

| Metric | Unconstrained result |
| --- | ---: |
| Accepted trades | 835 |
| Expectancy | 0.3042R |
| Profit factor | 1.7644 |
| Corrected maximum drawdown | -33.4002R |
| Maximum concurrent positions | 63 |
| Maximum open risk | 63.0R |

## Selected configurations

| Configuration | Accepted | Rejected | Expectancy | PF | Drawdown | Max positions | Max risk | Double-cost expectancy | Expectancy 95% CI | Approved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `positions_10__risk_10R__daily_1R__highest_confidence` | 251 | 584 | 0.4275R | 2.2550 | -12.4900R | 10 | 10.0R | 0.3944R | 0.2770 to 0.5771R | Yes |
| `positions_10__risk_5R__daily_5R__best_risk_reward` | 148 | 687 | 0.3325R | 1.8041 | -9.1302R | 7 | 5.0R | 0.2990R | 0.1287 to 0.5307R | Yes |

## Approval criteria

A combination passes only when expectancy is positive, profit factor exceeds 1, drawdown is at least 25% less severe than the baseline, observed open risk does not exceed 10R, observed positions do not exceed 10, double-cost expectancy and profit factor remain positive and above 1, and neither one sector nor one calendar year supplies 50% of gross positive R.

## Complete combination results

All 256 combinations, including win rate, average R, worst day, worst rolling five-day period, sector exposure, trades per year, bootstrap interval, rejection reasons, and double-cost performance are stored in the machine-readable artifact.

## Methodology

- The source is the frozen locked-holdout ledger. Signal generation, entry, stop, target, scoring, thresholds, and regime filtering are unchanged.
- Admission is evaluated at the actual entry session. Entries occur before same-session partial or final exits.
- Each new position contributes 1R of initial open risk. TP1 reduces remaining open risk in proportion to the remaining shares.
- A material drawdown improvement means at least 25% less severe than the corrected -33.4002R baseline.
- A configuration fails if one sector or calendar year contributes 50% or more of gross positive R.
- Bootstrap intervals use 5,000 deterministic resamples of trade R.
- Double-cost results rerun the frozen execution with doubled costs and slippage before applying the same constraints.

## Limitations

These combinations reuse one historical holdout ledger and therefore constitute a multiple-comparison experiment. A selected constraint set requires a new locked validation before production use. Open risk is expressed in initial R, not a mark-to-market volatility or gap-risk model. Because every frozen plan has the same 2R TP1, the best-risk/reward ranking cannot distinguish signals and resolves ties deterministically by ticker; its lowest-drawdown result must not be interpreted as evidence that risk/reward ranking adds value.

Machine-readable results: `artifacts/portfolio_constraint_results.json`.
