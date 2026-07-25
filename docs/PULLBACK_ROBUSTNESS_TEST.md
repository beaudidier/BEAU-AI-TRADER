# Pullback Strategy Robustness Test

## Scope

The unchanged 81-configuration robustness matrix was rerun across 110 cached liquid US stocks. Entries, stops, targets, the 5% per-trade risk rejection, costs, slippage, partial exits, and stop-first handling were not changed.

Every drawdown now aggregates dated TP1 and final exit legs by session. It is independent of ticker iteration.

## Corrected core results

The Milestone 28-style baseline produced 1,176 trades, 0.0739R expectancy, 1.1435 profit factor, and -130.5873R chronological drawdown. Its prior ticker-order drawdown was -36.4450R. Expectancy did not change.

The selected three-day, 1.5-ATR, 2R/4R configuration:

| Cost level | Trades | Expectancy | Profit factor | Win rate | Corrected drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Current | 605 | 0.1600R | 1.3290 | 46.78% | -54.8382R |
| Double | 575 | 0.1021R | 1.1997 | 45.39% | -57.0966R |
| Triple | 555 | 0.0735R | 1.1398 | 44.32% | -60.2487R |

## Chronological portfolio risk

| Metric | Result |
| --- | ---: |
| Maximum concurrent positions | 56 |
| Maximum open risk | 52.0R |
| Maximum daily new risk | 10.0R |
| Worst trading day | -9.8679R |
| Worst rolling five-day period | -18.6107R |
| Worst same-session gross loss | -10.5423R |

## Verdict

No configuration is approved for production. Positive expectancy survives in parts of the matrix, but unconstrained portfolio exposure and corrected drawdown are unacceptable. The strategy remains research and paper-trading only; the analysis-only 10R total / 10-position / 3R daily-new-risk limits are not enforced in production.

Machine-readable results: [pullback_robustness_results.json](/Users/beaudidier/Desktop/BEAU-AI-TRADER/artifacts/pullback_robustness_results.json).
