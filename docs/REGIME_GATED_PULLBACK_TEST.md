# Market-Regime Gated Pullback Test

## Scope

This is an experiment only. Production scoring, execution, and frontend behavior remain unchanged.

The test reuses the cached five-year, 110-stock US universe from the Pullback robustness audit. Every regime decision is evaluated at the signal close, before the next sessions can trade the selected Pullback entry: a three-candle wait for the signal-time EMA20 limit, a 1.5-ATR stop below the 20-session swing low, 2R/4R targets, 50% TP1 exit, original stop on the remainder, stop-first OHLC handling, and the existing slippage and transaction costs. The final chronological 30% of 113,410 raw signal dates is out of sample.

Filter D uses the free QQQ historical benchmark, cached locally alongside the existing data, as the Nasdaq-100 proxy. Filter E uses the contemporaneous share of the 110-stock test universe above its own EMA200. Filter F is the unchanged existing market-regime engine (`score >= 65`).

The complete result set is in [regime_gated_pullback_results.json](/Users/beaudidier/Desktop/BEAU-AI-TRADER/artifacts/regime_gated_pullback_results.json), and the ledger contains every exit leg plus every rejected signal and reason in [regime_gated_pullback_trades.csv](/Users/beaudidier/Desktop/BEAU-AI-TRADER/artifacts/regime_gated_pullback_trades.csv).

## Out-of-sample comparison

| Filter | Eligible signals | Accepted trades | Expectancy (R) | 95% CI | PF | Win rate | Max drawdown (R) | TP1 / TP2 / stop |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| Ungated | 34,023 | 167 | 0.1917 | -0.0004 to 0.3907 | 1.4268 | 50.30% | -9.8431 | 20.96% / 3.59% / 39.52% |
| A — SPY close > EMA200 | 30,030 | 165 | 0.1947 | 0.0033 to 0.3890 | 1.4339 | 50.30% | -9.8431 | 21.21% / 3.64% / 39.39% |
| B — SPY EMA50 > EMA200 | 31,823 | 167 | 0.1917 | -0.0004 to 0.3907 | 1.4268 | 50.30% | -9.8431 | 20.96% / 3.59% / 39.52% |
| C — SPY dual EMA | 29,150 | 165 | 0.1947 | 0.0033 to 0.3890 | 1.4339 | 50.30% | -9.8431 | 21.21% / 3.64% / 39.39% |
| D — QQQ close > EMA200 | 29,590 | 164 | 0.1902 | -0.0077 to 0.3958 | 1.4213 | 50.00% | -9.8431 | 21.34% / 3.66% / 39.63% |
| E — 60% universe breadth | 27,500 | 158 | 0.1780 | -0.0224 to 0.3868 | 1.3839 | 49.37% | -10.6418 | 20.89% / 3.80% / 41.77% |
| F — Existing regime engine | 26,070 | 151 | 0.2316 | 0.0257 to 0.4389 | 1.5406 | 52.32% | -9.0076 | 21.85% / 3.97% / 37.75% |

All filters retain more than 100 out-of-sample trades. Filter F is the only pre-defined filter whose out-of-sample expectancy interval is wholly positive. The filters are highly correlated in the final period, which is why several outcomes are nearly identical.

## Full-sample cost stress test

| Filter | Current-cost trades / expectancy / PF | Double-cost trades / expectancy / PF |
| --- | --- | --- |
| Ungated | 605 / 0.1600R / 1.3290 | 575 / 0.1021R / 1.1997 |
| A | 574 / 0.1901R / 1.3962 | 546 / 0.1213R / 1.2394 |
| B | 557 / 0.2289R / 1.4950 | 532 / 0.1616R / 1.3301 |
| C | 552 / 0.2286R / 1.4922 | 526 / 0.1558R / 1.3163 |
| D | 556 / 0.2301R / 1.4960 | 532 / 0.1591R / 1.3234 |
| E | 538 / 0.1953R / 1.4098 | 517 / 0.1289R / 1.2546 |
| F | 553 / 0.1806R / 1.3778 | 529 / 0.1113R / 1.2188 |

Every gated filter has a double-cost PF above one. This is a useful stress result, but it is not sufficient evidence to deploy a strategy.

## Filter F detail

Filter F is mechanically strongest. Its 553 full-sample trades have 0.1806R expectancy, 1.3778 PF, 47.74% win rate, -12.1999R maximum drawdown, and a 0.0665R to 0.2944R bootstrap interval. Its out-of-sample 151 trades have 0.2316R expectancy, 1.5406 PF, and a 0.0257R to 0.4389R interval. Double costs reduce it to 0.1113R expectancy, 1.2188 PF, and -18.5808R drawdown.

Its sector distribution is not controlled by one sector: the largest positive contribution is Communication Services (37 trades, 0.5497R), while Consumer Staples supplies 117 trades at 0.0494R. Consumer Discretionary is negative (39 trades, -0.0601R), and several sectors have wide intervals because of modest samples. Its two chronological periods are positive: calibration has 402 trades at 0.1615R; out of sample has 151 at 0.2316R.

## Baseline comparison

Over the same final out-of-sample interval, equal-weight buy-and-hold across the 110 stocks returned an average 30.0809% with a 73.64% constituent win rate. The EMA20/EMA50 crossover baseline produced 422 thirty-session observations with 1.9690% average return and 56.40% win rate. Matched random entries produced 167 observations with 0.7573% average return and 55.69% win rate.

These are return-based baselines, not R-multiple strategies with stops and partial exits, so they are directional context rather than directly interchangeable performance measures. The audit does not claim that Filter F beats buy-and-hold.

## Verdict

No regime filter is approved for production. Filter F mechanically passes the stated acceptance checks: it has over 100 out-of-sample trades, a positive out-of-sample expectancy interval, double-cost PF above one, and no single sector or period contributing most of the profit. However, this audit selected the apparent winner from six related filters using the same dataset. That selection is itself a form of test-period fitting.

The next valid test is a pre-registered, locked forward period for Filter F alone. Until then, the result supports paper-only research—not a production strategy change.
