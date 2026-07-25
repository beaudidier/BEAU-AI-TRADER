# Locked Holdout Validation

## Validation status

The frozen strategy was tested on an unused five-year historical window from **2016-07-01 through 2021-07-10**, entirely before the 2021-07-12 through 2026-07-23 research data used by Milestones 28–30. It uses 108 validated liquid US stocks across eleven sectors; no symbol was removed for performance.

This is a non-overlapping retrospective holdout, not a future-forward test. It provides independent historical evidence, but it cannot replace a new live or post-selection chronological period because the strategy was selected using later dates.

The strategy is frozen exactly as selected in Milestone 30: existing market-regime engine filter (`score >= 65`), three-session EMA20 limit wait, 1.5-ATR stop below the 20-session swing low, 2R/4R targets, 50% TP1 exit, original stop on the remaining shares, same slippage and transaction costs, stop-first handling, and one position per ticker.

## Frozen strategy results

| Metric | Result |
| --- | ---: |
| Eligible signals | 89,208 |
| Accepted trades | 835 |
| Rejected trades | 110,513 |
| Trades per year | 318.69 |
| Expectancy / average R | 0.3042R |
| Bootstrap 95% expectancy CI | 0.2216R to 0.3875R |
| Profit factor | 1.7644 |
| Win rate | 55.93% |
| Maximum drawdown | -10.4094R |
| TP1 rate | 21.44% |
| TP2 rate | 1.08% |
| Stop rate | 36.89% |

Under double costs, the strategy still produced 816 trades, 0.2638R expectancy, 1.6391 PF, -11.1109R maximum drawdown, and a 0.1791R to 0.3466R expectancy interval.

The largest positive sector contribution was Financials, but it represented only 16.31% of aggregate positive expectancy, below the 50% concentration rejection threshold. Sector evidence is broad but uneven: Financials (68 trades, 0.6094R), Materials (53, 0.5389R), Technology (51, 0.4780R), and Industrials (70, 0.4229R) were strongest; Communication Services was weak (62, 0.0643R). Several individual sector confidence intervals remain wide.

## Market-regime breakdown

| Regime | Trades | Expectancy | PF | Notes |
| --- | ---: | ---: | ---: | --- |
| Bull | 829 | 0.3045R | 1.7656 | Dominant eligible regime; 95% CI 0.2198R to 0.3894R |
| Bear | 1 | -1.0298R | 0.0000 | Filter correctly excluded almost all bear signals; sample is not informative |
| Sideways | 5 | 0.5280R | 2.6841 | Sample is too small to interpret |

The filter's purpose is visible here: it avoids almost all Bear and Sideways long entries. That means this holdout validates a regime-gated long strategy, not its ability to trade all market states.

## Comparisons

| Approach | Trades / observations | Expectancy or average return | PF / win rate |
| --- | ---: | ---: | --- |
| Frozen gated Pullback | 835 | 0.3042R | PF 1.7644; 55.93% win rate |
| Ungated Pullback | 878 | 0.3206R | PF 1.8146; 56.15% win rate |
| Buy and hold | 108 | 117.7451% average return | 90.74% constituent win rate |
| EMA20/EMA50 crossover | 1,155 | 2.1477% average 30-session return | 61.21% win rate |
| Matched random entries | 878 | 2.0755% average 30-session return | 65.15% win rate |

The three baselines are return-based, while the Pullback results are R-multiple, stop-managed trades; they provide directional context rather than directly interchangeable performance measures. This result does not establish outperformance versus buy-and-hold.

## Approval assessment

The frozen gated strategy meets every mechanical holdout criterion: more than 100 trades, positive expectancy, PF above one, a non-negative expectancy confidence interval, diversified sector contribution, and profitability under double costs.

**Do not make a production change.** The result is supportive but retrospective: the test period precedes the data used to select the filter. The next required validation is a truly future-forward, locked period after 2026-07-23, with no changes to the frozen strategy.

Full machine-readable results: [locked_holdout_results.json](/Users/beaudidier/Desktop/BEAU-AI-TRADER/artifacts/locked_holdout_results.json). Complete ledger: [locked_holdout_trades.csv](/Users/beaudidier/Desktop/BEAU-AI-TRADER/artifacts/locked_holdout_trades.csv).
