# Backtest Integrity Audit

## Scope and method

This audit reproduced every trade in `artifacts/ai_calibration_trades.csv` from the cached raw daily OHLCV files in `artifacts/calibration_dataset/`. It did not change scoring, thresholds, weights, or execution code.

- Recorded ledger trades replayed: **999 / 999 exact matches**
- Out-of-sample trades replayed: **300 / 300 exact matches**
- Replay failures: **0**
- Out-of-sample split: chronological final 30% of the recorded ledger
- Bootstrap: **10,000** seeded resamples per confidence band; seed `20260725`

“Exact match” means the raw-data replay reproduced the recorded entry mechanics, stop/target flags, exit price, return percentage, R multiple, MFE, and MAE. It establishes that the artifact matches the current code. It does not establish that the code represents an economically complete partial-target strategy.

## Execution verification

| Check | Result |
| --- | ---: |
| Next-candle-open entries with configured entry slippage | 300 / 300 OOS trades |
| Stop exits | 75 |
| Target 2 exits | 151 |
| 30-session mark-to-market exits | 74 |
| Same-candle stop/target ambiguities | 0 |
| Same-ticker duplicate/overlapping positions | 0 |
| Incomplete positions counted | 0 |
| TP1 hits | 202 |
| TP2 hits | 151 |
| Partial exits recorded at TP1 | 0 |
| Remaining-position tracking after TP1 | No |
| TP1 hits with non-positive final R | 37 |
| TP1 hits with positive final R | 165 |
| Target 1 at or below actual next-open fill | 33 |
| Target 2 at or below actual next-open fill | 1 |

### Entry, stops, targets, and same-candle handling

The signal is generated using data through the prior close. The recorded entry is the next daily candle’s open multiplied by `1.0005` (5 bps slippage). Each simulator candle checks the stop before targets, so a candle that touches both would be recorded as a stop. No such ambiguity occurred in the 300 out-of-sample trades.

The simulator checks TP1 and TP2 against the candle high. It closes the entire position at TP2; otherwise it closes the entire position at the stop or at the close after 30 sessions. TP1 only sets a boolean. It does not realize any P/L and no reduced remaining position exists in the calibration ledger.

### Costs and R multiple

The code applies 5 bps slippage to the entry fill, then subtracts `(5 bps slippage + 5 bps transaction cost)` at both entry and exit in its cost formula. That is 20 bps in the cost formula plus the separately increased entry fill, approximately 25 bps round trip near equal entry and exit prices. This is the exact implemented calculation, not a recommendation.

Recorded R is:

```text
(exit price − next-open fill − calculated costs) / (next-open fill − planned stop)
```

The targets are calculated from the prior-close plan entry, while R uses the next-open fill. On 33 OOS trades, target 1 was already at or below that actual fill; on one trade, so was target 2. This can produce a target flag without a reward relative to the actual entry.

Win/loss classification is final R greater than zero. Maximum drawdown now aggregates dated partial and final exit legs into daily realised R before calculating the portfolio equity path. It remains an equal-risk R analysis rather than a capital-weighted brokerage account.

## Out-of-sample confidence-band results and bootstrap intervals

Point estimates are the existing out-of-sample calibration values. The intervals are non-parametric bootstrap 95% confidence intervals.

| Band | Trades | Win rate | Win-rate 95% CI | Expectancy (R) | Expectancy 95% CI | Profit factor | PF 95% CI | Average R | Average-R 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SKIP (0–59) | 72 | 51.39% | 40.2778%–62.5000% | 0.6346 | 0.2148–1.0743 | 2.3692 | 1.3832–3.9717 | 0.6346 | 0.2148–1.0743 |
| WATCH (60–74) | 128 | 57.03% | 48.4375%–65.6250% | -0.0439 | -0.1920–0.1093 | 0.8683 | 0.5192–1.3968 | -0.0439 | -0.1920–0.1093 |
| BUY (75–89) | 100 | 76.00% | 67.0000%–84.0000% | 0.0359 | -0.0584–0.1229 | 1.2112 | 0.7554–2.1428 | 0.0359 | -0.0584–0.1229 |
| STRONG BUY (90–100) | 0 | — | — | — | — | — | — | — | — |

### Why BUY has a 76% win rate but only 0.0359R expectancy

The 100 BUY trades contain 76 positive-R outcomes averaging **+0.2713R** and 24 non-positive outcomes averaging **-0.7093R**. Thus, the frequent winners are much smaller than the less-frequent losses. Their combined total is only **+3.5950R**, or **+0.0359R per trade**.

The execution treatment reinforces that imbalance: TP1 was hit but final R was non-positive on **18 BUY trades**. Since the simulator records no partial profit at TP1, a later stop or unfavorable time-cap close can turn a flagged TP1 trade into a final loss. The BUY expectancy interval also crosses zero, so the observed positive point estimate is not conclusive.

### Why SKIP has positive expectancy

The 72 SKIP trades contain 37 positive-R outcomes averaging **+2.1367R** and 35 non-positive outcomes averaging **-0.9534R**, for **+45.6877R** total or **+0.6346R per trade**. Its bootstrap expectancy interval is positive in this one sample.

This does not validate taking SKIP trades. The result is non-monotonic across score bands, comes from one 30-stock historical sample, and uses the incomplete TP1 accounting described above. It shows that this calibration run does not support confidence rank as a reliable ordering of economic outcomes.

### Why TP1 hit rate can exceed win rate

TP1 is a candle-high event flag, not an exit. It may be set and then followed by a stop or a negative time-cap close, because no quantity is sold at TP1. Across OOS trades, **202** TP1 flags produced only **165** positive final-R trades; **37** TP1 flags ended non-positive. In BUY specifically, TP1 hit rate is **94.00%**, win rate is **76.00%**, and **18** TP1-flagged trades ended non-positive.

## Baseline comparisons

All baseline return figures use the same cost formula as the ledger. Their return percentages are not R multiples unless stated otherwise.

| Baseline | Trades | Win rate | Average return | Profit factor | Definition |
| --- | ---: | ---: | ---: | ---: | --- |
| Buy and hold, equal weight | 30 | 76.6667% | 10.3223% | 2.9524 | One long position per ticker from the first OOS entry date to the final OOS exit date. |
| EMA20/EMA50 crossover | 49 | 40.8163% | 1.4167% | 1.3444 | Long on an upward daily crossover; exit on downward crossover or 30 sessions. |
| Random matched | 300 | 58.6667% | 0.8840% | 1.4172 | Seeded random entries matched to each trade’s ticker, calendar month, holding time, and total trade count. |
| All valid setups, no confidence filter | 300 | 62.0000% | 0.5422% | 1.1919 | All generated OOS plans across every score band; average R is 0.1455. |

The all-setups and random comparisons use different return units from the calibration R-profit-factor statistic, so their PF values must not be compared numerically with the R-based confidence-band PFs. They are directional baselines only, not a claim of statistical superiority.

## Trustworthiness verdict

The results are **mechanically reproducible**: the complete 999-trade ledger matches the cached raw OHLCV data and current simulator exactly. They are **not yet trustworthy as evidence that the confidence thresholds predict tradable performance**.

Reasons:

- TP1 accounting does not model the stated partial-exit workflow, so target-hit statistics and final P/L are not economically aligned.
- The planned entry/targets are based on the prior close while performance is measured from the next-open fill, creating 33 OOS target-1 cases with no reward from the actual fill.
- BUY expectancy and profit-factor bootstrap intervals include break-even or loss; STRONG BUY has no observations.
- SKIP outperforms BUY in this sample, contradicting the intended confidence ordering.
- Drawdown is now chronological portfolio realised R, but positions remain unconstrained by total capital or open risk.
- The baselines are descriptive and the sample is limited to one cached historical universe and period.

No simulation, scoring, threshold, or weight changes were made by this audit.
