# Locked Holdout Validation

## Validation status

The frozen strategy was rerun on the unchanged non-overlapping 2016-07-01 through 2021-07-10 holdout. Signal generation, the regime gate, EMA20 pullback entry, 1.5-ATR stop, 2R/4R targets, 50% TP1 exit, costs, slippage, stop-first handling, and per-ticker overlap prevention are unchanged.

The signal edge still passes its original statistical checks. The portfolio does **not** pass risk validation because the unconstrained historical book exceeded the analysis-only limits.

## Corrected results

| Metric | Result |
| --- | ---: |
| Eligible signals | 89,208 |
| Accepted trades | 835 |
| Rejected trades | 110,513 |
| Trades per year | 204.55 |
| Expectancy / average R | 0.3042R |
| Bootstrap expectancy 95% CI | 0.2216R to 0.3875R |
| Profit factor | 1.7644 |
| Win rate | 55.93% |
| Old ticker-order drawdown | -10.4094R |
| Corrected chronological drawdown | -33.4002R |
| Maximum concurrent positions | 63 |
| Maximum simultaneous open risk | 63.0R |
| Maximum daily new risk | 17.0R |
| Worst trading day | -12.3999R on 2018-10-11 |
| Worst rolling five-day period | -25.3579R |
| Worst same-session gross loss | -12.3999R |

Under double costs, 816 trades retain 0.2638R expectancy and 1.6391 profit factor, while corrected drawdown is -32.3360R.

## Why drawdown changed

The old calculation accumulated one final R result at a time in ticker-processing order. The corrected engine places the entry, TP1 leg, final exit, costs, and slippage on their actual sessions; aggregates same-day realised P/L; and calculates cumulative R and drawdown from that daily portfolio path. Expectancy and profit factor did not change because the same net exit-leg outcomes are still summed.

## Portfolio-risk verdict

At 1% account risk per initial 1R trade, the observed 63.0R peak represents approximately 63.0% simultaneous initial risk. That is not acceptable for production. For the next analysis experiment, cap total open risk at **10R**, concurrent positions at **10**, and daily new risk at **3R**. These limits are reported only and are not enforced in production.

The strategy remains paper-trading and forward-validation only.

Machine-readable results: [locked_holdout_results.json](/Users/beaudidier/Desktop/BEAU-AI-TRADER/artifacts/locked_holdout_results.json).
