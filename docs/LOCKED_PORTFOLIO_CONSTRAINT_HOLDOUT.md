# Locked Portfolio Constraint Holdout

## Executive verdict

The frozen 10-position / 10R / 1R-daily portfolio passes the later chronological constraint holdout. No production constraint was enabled.

Expectancy is **0.1604R**, profit factor is **1.3484**, and corrected maximum drawdown is **-25.9138R** versus **-53.6149R** unconstrained.

## Frozen configuration

- Maximum concurrent positions: **10**
- Maximum total open risk: **10R**
- Maximum daily new risk: **1R**
- Ranking: **signal-time confidence**
- Strategy: **frozen Regime-Gated Pullback**

## Holdout separation

Milestone 47 ended on **2021-07-10**. This constraint holdout uses cached data from **2021-07-12** through **2026-07-23**, with no overlap.

## Strategy comparison

| Portfolio | Accepted | Portfolio-rejected | Expectancy | PF | Win rate | Drawdown | Max risk | Max positions | Trades/year | Expectancy 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Frozen 10 / 10R / 1R | 247 | 306 | 0.1604R | 1.3484 | 48.18% | -25.9138R | 10.0R | 10 | 49.11 | 0.0069 to 0.3193R |
| Unconstrained | 553 | 0 | 0.1806R | 1.3778 | 47.74% | -53.6149R | 44.0R | 44 | 109.95 | 0.0742 to 0.2885R |
| Comparator 10 / 10R / 3R | 281 | 272 | 0.1568R | 1.3268 | 47.69% | -36.9233R | 10.0R | 10 | 55.87 | 0.0071 to 0.3089R |

## Tail risk and exposure

| Metric | Frozen result |
| --- | ---: |
| Worst trading day | -2.4267R on 2023-09-28 |
| Worst rolling five-day period | -4.4996R (2023-09-26 to 2023-10-02) |
| Peak single-sector active share | 100.00% (Health Care) |

### Average active sector exposure

| Sector | Average active share |
| --- | ---: |
| Consumer Staples | 19.69% |
| Consumer Discretionary | 12.39% |
| Health Care | 11.53% |
| Utilities | 9.75% |
| Communication Services | 9.29% |
| Real Estate | 8.83% |
| Industrials | 8.43% |
| Financials | 6.68% |
| Materials | 6.20% |
| Energy | 3.94% |
| Technology | 3.27% |

## Double-cost performance

The frozen constraints accept 245 trades at doubled costs, with **0.0978R** expectancy, **1.1955** profit factor, and **-24.9742R** drawdown.

## Baselines

- Equal-weight buy and hold: 96.63% total return and -18.16% maximum drawdown.
- Matched random entries: 247 observations, 0.5589% average return, and 57.09% win rate.

Baseline returns are percentages, while strategy results are R-multiples; they provide context but are not the same unit.

## Approval criteria

- PASS — positive expectancy
- PASS — profit factor above one
- PASS — materially lower drawdown
- PASS — maximum open risk at most 10R
- PASS — maximum positions at most 10
- PASS — profitable under double costs
- PASS — expectancy interval not materially negative

## Limitations

This is a locked test of portfolio constraints, not a fresh validation of the underlying strategy: the later dataset was used in earlier strategy research but was not used to select the Milestone 47 portfolio limits. The constraints remain research-only until an explicit production decision.

Machine-readable results: `artifacts/locked_portfolio_constraint_results.json`.
