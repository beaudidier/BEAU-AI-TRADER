# Calibration Decision

The executable-entry rerun rejects gap-invalid setups before execution and recalculates all plan levels from the next-open fill. No decision threshold, score, or weight changed.

| Verdict | Accepted trades | Expectancy | Profit factor | Maximum drawdown | Bootstrap expectancy 95% CI |
| --- | ---: | ---: | ---: | ---: | --- |
| SKIP | 76 | 0.4259R | 1.7374 | -16.2608R | 0.0494R–0.8721R |
| WATCH | 89 | 0.2197R | 1.3893 | -13.0953R | -0.1120R–0.5184R |
| BUY | 21 | -0.0531R | 0.9282 | -6.3877R | -0.7070R–0.6137R |
| STRONG BUY | 0 | N/A | N/A | N/A | N/A |

The current thresholds must not change based on this run. BUY is worse than WATCH on expectancy and profit factor and has only 21 accepted OOS trades. The score ordering is not supported after executable-entry validation.
