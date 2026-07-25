# Sector Concentration Impact Audit

## Executive verdict

The best expectancy came from **A. No sector limit**. The smallest maximum drawdown came from **E. Highest-confidence signal per sector per day**.

No concentration control is statistically justified on this single retrospective holdout: the paired intervals do not prove both preserved expectancy and lower drawdown.

This is a retrospective portfolio-admission audit of the frozen locked-holdout strategy. It does not change production behavior, signal generation, entries, stops, targets, scoring, or market-regime rules.

## Dataset and method

- Locked holdout signals: **835** trades across **101** stocks and **11** sectors.
- Period: **2017-04-19** through **2021-06-30**.
- Every trade keeps its original entry, stop, targets, partial exits, slippage, costs, and final R.
- Confidence for Variant E is reconstructed only from candles available at signal close.
- Entry and exit dates both count as active, which treats same-day overlap conservatively.
- A literal percentage cap cannot start from an empty portfolio because its first position is 100%. During this unavoidable startup state, only additions that strictly reduce concentration are accepted. Once the active book reaches the cap, the cap is enforced directly.
- Worst simultaneous loss is the gross negative R from exit legs realised on the same session; same-day winning legs do not offset it.
- Variant-minus-baseline intervals use a paired moving-block bootstrap of chronologically realised trades (20-trade blocks, 10,000 samples).
- The no-limit expectancy (0.3042R), profit factor (1.7644), win rate (55.93%), and trade count (835) exactly reproduce the locked result.

### Drawdown audit finding

The previous sector audit reported **-29.4789R** using final trade outcomes ordered by final exit date. The corrected engine places every TP1 and final exit leg on its actual session, aggregates same-day portfolio P/L, and reports **-33.4002R**. The older locked holdout's ticker-order figure was **-10.4094R**. No trade outcome or production strategy rule changed.

## Variant results

| Variant | Trades | Rejected | Expectancy | Profit factor | Win rate | Average R | Max drawdown | Worst simultaneous loss | Max concurrent | 95% expectancy CI | Double-cost expectancy | Double-cost PF |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| A. No sector limit | 835 | 0 | 0.3042R | 1.7644 | 55.93% | 0.3042R | -33.4002R | -12.3999R | 63 | 0.2225R to 0.3873R | 0.2638R | 1.6391 |
| B. Maximum 30% in one sector | 784 | 51 | 0.3011R | 1.7495 | 55.48% | 0.3011R | -31.8521R | -12.3999R | 63 | 0.2143R to 0.3875R | 0.2651R | 1.6370 |
| C. Maximum 40% in one sector | 811 | 24 | 0.3040R | 1.7610 | 55.86% | 0.3040R | -30.0040R | -12.3999R | 63 | 0.2209R to 0.3873R | 0.2615R | 1.6291 |
| D. Maximum 50% in related rate-sensitive sectors | 829 | 6 | 0.3024R | 1.7545 | 55.61% | 0.3024R | -33.4002R | -12.3999R | 63 | 0.2188R to 0.3876R | 0.2624R | 1.6301 |
| E. Highest-confidence signal per sector per day | 740 | 95 | 0.2873R | 1.7129 | 55.14% | 0.2873R | -28.6717R | -12.3999R | 54 | 0.2003R to 0.3736R | 0.2405R | 1.5723 |

## Paired comparison with no sector limit

Positive drawdown improvement means a smaller loss. Intervals include the dependency between each original trade and the rule that retained or rejected it.

| Variant | Expectancy difference | 95% CI | Drawdown improvement | 95% CI |
|---|---:|---|---:|---|
| A. No sector limit | +0.0000R | +0.0000R to +0.0000R | +0.0000R | +0.0000R to +0.0000R |
| B. Maximum 30% in one sector | -0.0031R | -0.0318R to +0.0211R | +1.5481R | -5.1282R to +6.0523R |
| C. Maximum 40% in one sector | -0.0002R | -0.0189R to +0.0193R | +3.3962R | -3.1195R to +4.4291R |
| D. Maximum 50% in related rate-sensitive sectors | -0.0018R | -0.0059R to +0.0002R | +0.0000R | -2.5001R to +0.0000R |
| E. Highest-confidence signal per sector per day | -0.0169R | -0.0527R to +0.0157R | +4.7285R | +0.1457R to +11.0367R |

## Performance by market regime

### A. No sector limit

| Regime | Trades | Expectancy | Profit factor | Win rate | Max drawdown | 95% expectancy CI |
|---|---:|---:|---:|---:|---:|---|
| Bear | 1 | -1.0298R | 0.0000 | 0.00% | -1.0298R | -1.0298R to -1.0298R |
| Bull | 829 | 0.3045R | 1.7656 | 55.97% | -33.4002R | 0.2229R to 0.3891R |
| Sideways | 5 | 0.5280R | 2.6841 | 60.00% | -1.5674R | -0.5488R to 1.6123R |

### B. Maximum 30% in one sector

| Regime | Trades | Expectancy | Profit factor | Win rate | Max drawdown | 95% expectancy CI |
|---|---:|---:|---:|---:|---:|---|
| Bear | 1 | -1.0298R | 0.0000 | 0.00% | -1.0298R | -1.0298R to -1.0298R |
| Bull | 779 | 0.3040R | 1.7582 | 55.58% | -31.8521R | 0.2177R to 0.3897R |
| Sideways | 4 | 0.0622R | 1.1588 | 50.00% | -1.5674R | -0.7837R to 0.9351R |

### C. Maximum 40% in one sector

| Regime | Trades | Expectancy | Profit factor | Win rate | Max drawdown | 95% expectancy CI |
|---|---:|---:|---:|---:|---:|---|
| Bear | 1 | -1.0298R | 0.0000 | 0.00% | -1.0298R | -1.0298R to -1.0298R |
| Bull | 806 | 0.3069R | 1.7696 | 55.96% | -30.0040R | 0.2213R to 0.3892R |
| Sideways | 4 | 0.0622R | 1.1588 | 50.00% | -1.5674R | -0.7837R to 0.9351R |

### D. Maximum 50% in related rate-sensitive sectors

| Regime | Trades | Expectancy | Profit factor | Win rate | Max drawdown | 95% expectancy CI |
|---|---:|---:|---:|---:|---:|---|
| Bear | 1 | -1.0298R | 0.0000 | 0.00% | -1.0298R | -1.0298R to -1.0298R |
| Bull | 823 | 0.3027R | 1.7556 | 55.65% | -33.4002R | 0.2205R to 0.3862R |
| Sideways | 5 | 0.5280R | 2.6841 | 60.00% | -1.5674R | -0.5488R to 1.6123R |

### E. Highest-confidence signal per sector per day

| Regime | Trades | Expectancy | Profit factor | Win rate | Max drawdown | 95% expectancy CI |
|---|---:|---:|---:|---:|---:|---|
| Bear | 1 | -1.0298R | 0.0000 | 0.00% | -1.0298R | -1.0298R to -1.0298R |
| Bull | 734 | 0.2874R | 1.7137 | 55.18% | -28.6717R | 0.2003R to 0.3771R |
| Sideways | 5 | 0.5280R | 2.6841 | 60.00% | -1.5674R | -0.5488R to 1.6123R |

## Utilities and Real Estate

| Variant | Trades | Share of trades | Expectancy | Total R | Share of positive R | Share of loss R |
|---|---:|---:|---:|---:|---:|---:|
| A. No sector limit | 211 | 25.27% | 0.2180R | 45.9878R | 22.35% | 25.59% |
| B. Maximum 30% in one sector | 192 | 24.49% | 0.1624R | 31.1783R | 20.52% | 26.00% |
| C. Maximum 40% in one sector | 204 | 25.15% | 0.1856R | 37.8594R | 21.54% | 26.24% |
| D. Maximum 50% in related rate-sensitive sectors | 205 | 24.73% | 0.2082R | 42.6870R | 21.91% | 25.59% |
| E. Highest-confidence signal per sector per day | 172 | 23.24% | 0.1418R | 24.3855R | 19.31% | 24.90% |

In the no-limit ledger, Utilities and Real Estate were **25.27%** of trades, produced **22.35%** of gross positive R, and produced **25.59%** of gross loss R. They did not create a disproportionate share of profit or loss. Their combined expectancy (**0.2180R**) was below the portfolio expectancy (**0.3042R**).

| Sector | Trades | Expectancy | Profit factor | Win rate | Total R | 95% expectancy CI |
|---|---:|---:|---:|---:|---:|---|
| Real Estate | 90 | 0.2196R | 1.4986 | 52.22% | 19.7653R | -0.0256R to 0.4765R |
| Utilities | 121 | 0.2167R | 1.5778 | 58.68% | 26.2225R | 0.0280R to 0.4102R |

## Simultaneous-trade correlation

In the uncapped ledger, 23722 overlapping trade pairs had at least three shared sessions. Mean daily-return correlation was **0.2226** overall, **0.4533** within the same sector, and **0.4500** for Utilities/Real Estate pairs.

These are correlations of split-adjusted underlying daily close returns while both trades were open. They are not correlations of final trade R and do not model intraday covariance.

## Sector exposure over time

The machine-readable artifact contains monthly exposure histories and per-sector peak/average active shares for every variant. Key peak exposures are:

| Variant | Leading sector | Peak share | Peak active positions | Trading days above 30% |
|---|---|---:|---:|---:|
| A. No sector limit | Consumer Staples | 100.00% | 10 | 185 |
| B. Maximum 30% in one sector | Consumer Staples | 100.00% | 10 | 127 |
| C. Maximum 40% in one sector | Consumer Staples | 100.00% | 10 | 164 |
| D. Maximum 50% in related rate-sensitive sectors | Consumer Staples | 100.00% | 10 | 200 |
| E. Highest-confidence signal per sector per day | Real Estate | 100.00% | 10 | 29 |

## Interpretation

- **B. Maximum 30% in one sector** rejected **51** signals, changed expectancy by **-0.0031R**, and improved maximum drawdown by **+1.5481R**. The paired expectancy-difference interval was **-0.0318R to +0.0211R**; the paired drawdown-improvement interval was **-5.1282R to +6.0523R**.
- **C. Maximum 40% in one sector** rejected **24** signals, changed expectancy by **-0.0002R**, and improved maximum drawdown by **+3.3962R**. The paired expectancy-difference interval was **-0.0189R to +0.0193R**; the paired drawdown-improvement interval was **-3.1195R to +4.4291R**.
- **D. Maximum 50% in related rate-sensitive sectors** rejected **6** signals, changed expectancy by **-0.0018R**, and improved maximum drawdown by **+0.0000R**. The paired expectancy-difference interval was **-0.0059R to +0.0002R**; the paired drawdown-improvement interval was **-2.5001R to +0.0000R**.
- **E. Highest-confidence signal per sector per day** rejected **95** signals, changed expectancy by **-0.0169R**, and improved maximum drawdown by **+4.7285R**. The paired expectancy-difference interval was **-0.0527R to +0.0157R**; the paired drawdown-improvement interval was **+0.1457R to +11.0367R**.

**Conclusion:** Variant C provides the strongest exploratory balance: it rejected 24 trades, left expectancy effectively unchanged, and reduced the observed chronological drawdown by 3.3962R. Variant E had the smallest observed drawdown but gave up 0.0169R expectancy and rejected 95 trades. The paired intervals and the reuse of one holdout do not establish that either improvement will persist. Sector concentration controls are therefore **not statistically justified for production yet**.

The audit does not implement a sector cap. Any future control would need a separately locked validation because comparing five alternatives on the same holdout introduces selection risk.

## Limitations

- The ledger contains equal-risk R outcomes, not a fully capital-constrained brokerage portfolio.
- The startup-safe cap convention is explicit but is one possible implementation of percentage limits.
- Worst simultaneous loss is realised gross loss by session; intraday and unrealised mark-to-market loss may differ.
- Maximum drawdown is a chronological realised-R sequence without capital allocation or mark-to-market accounting.
- Confidence reconstruction uses the current deterministic institutional engine on historical signal-close data. It is not a probability.
- Five variants are compared on one locked historical window, so the apparent winner is not independently validated.
- Sector labels are the frozen research-universe labels and are not point-in-time constituent classifications.

Machine-readable results: `artifacts/sector_concentration_results.json`.
