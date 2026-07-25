# Chronological Portfolio Risk Audit

## Executive verdict

The strategy's per-trade expectancy did not change, but the previous portfolio drawdowns were not trustworthy because several research runners accumulated trades in ticker-processing order. Every research metric now uses dated entry, partial-exit, and final-exit events with same-session P/L aggregation.

The locked holdout changes from **-10.4094R** to **-33.4002R**. It reached **63 simultaneous positions** and **63.0R** of open initial risk. The signal edge remains positive; the unconstrained portfolio risk is not acceptable.

## Corrected headline results

| Study | Old drawdown | Corrected drawdown | Expectancy before | Expectancy after |
| --- | ---: | ---: | ---: | ---: |
| Locked holdout | -10.4094R | -33.4002R | 0.3042R | 0.3042R |
| Pullback robustness baseline | -36.4450R | -130.5873R | 0.0739R | 0.0739R |
| Regime-gated selected filter | -12.1999R | -53.6149R | 0.1806R | 0.1806R |
| Sector audit, no limit | -29.4789R | -33.4002R | 0.3042R | 0.3042R |

## Locked-holdout portfolio path

| Metric | Corrected result |
| --- | ---: |
| Cumulative R | 254.0085R |
| Maximum drawdown | -33.4002R |
| Maximum concurrent positions | 63 |
| Maximum simultaneous open risk | 63.0R |
| Maximum daily new risk | 17.0R |
| Worst trading day | -12.3999R on 2018-10-11 |
| Worst rolling five-day period | -25.3579R |
| Worst same-session gross loss | -12.3999R |

## Why the numbers changed

The old implementations generally appended all trades for one ticker before moving to the next ticker, then applied a cumulative sum. That sequence is deterministic but not chronological. A later partial fix sorted only final trade outcomes by exit date, which still placed TP1 profit on the final-exit session.

The new engine builds one immutable event stream ordered by timestamp, entry, partial exit, and final exit. Entry and exit transaction costs and adverse slippage remain included in each leg's realised R. Same-day exit legs are aggregated before cumulative R and drawdown are updated, removing arbitrary ticker tie-breaking.

## Analysis-only portfolio constraints

- Maximum total open risk: **10R**
- Maximum concurrent positions: **10**
- Maximum daily new risk: **3R**

At 1% risk per trade, 10R corresponds to approximately 10% simultaneous initial account risk. The locked ledger reached 63R, so the recommendation is materially below observed exposure. These limits are not enforced in production and require a separate experiment before adoption.

## Validation verdict

The signal expectancy remains validated at 0.3042R with a 1.7644 profit factor. The overall strategy does **not** pass portfolio-risk validation because maximum drawdown, concurrent positions, total open risk, and daily new risk exceed the analysis limits.

Keep the strategy paper-trading and forward-validation only.

Machine-readable results: [chronological_portfolio_risk_results.json](/Users/beaudidier/Desktop/BEAU-AI-TRADER/artifacts/chronological_portfolio_risk_results.json).
