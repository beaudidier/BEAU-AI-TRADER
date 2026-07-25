# Market-Regime Gated Pullback Test

## Scope

The unchanged six-filter experiment was rerun using actual entry and exit-leg dates. Production scoring, filters, entries, stops, targets, costs, and execution remain unchanged.

## Corrected out-of-sample comparison

| Filter | Trades | Expectancy | PF | Win rate | Corrected drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ungated | 167 | 0.1917R | 1.4268 | 50.30% | -11.2682R |
| A — SPY close > EMA200 | 165 | 0.1947R | 1.4339 | 50.30% | -10.2512R |
| B — SPY EMA50 > EMA200 | 167 | 0.1917R | 1.4268 | 50.30% | -11.2682R |
| C — SPY dual EMA | 165 | 0.1947R | 1.4339 | 50.30% | -10.2512R |
| D — QQQ close > EMA200 | 164 | 0.1902R | 1.4213 | 50.00% | -10.2512R |
| E — 60% universe breadth | 158 | 0.1780R | 1.3839 | 49.37% | -10.1889R |
| F — Existing regime engine | 151 | 0.2316R | 1.5406 | 52.32% | -5.7980R |

## Filter F chronological risk

Full-sample expectancy remains **0.1806R** and profit factor remains **1.3778**. Drawdown changes from **-12.1999R** to **-53.6149R** because the old result accumulated ticker-ordered final outcomes.

Out of sample, drawdown changes from **-9.0076R** to **-5.7980R**. Double-cost full-sample drawdown changes from **-18.5808R** to **-57.9167R**.

| Metric | Full sample | Out of sample |
| --- | ---: | ---: |
| Maximum concurrent positions | 44 | 37 |
| Maximum open risk | 44.0R | 36.5R |
| Maximum daily new risk | 8.0R | 5.0R |
| Worst trading day | -4.1308R | -3.2595R |
| Worst rolling five days | -13.6276R | -4.1201R |

## Verdict

Filter F retains a positive out-of-sample expectancy interval and remains the mechanically strongest signal filter. It is not approved for production because the full unconstrained portfolio reached excessive concurrent risk. Continue paper-only forward validation. The 10R total / 10-position / 3R daily-new-risk limits are analysis recommendations only.

Machine-readable results: [regime_gated_pullback_results.json](/Users/beaudidier/Desktop/BEAU-AI-TRADER/artifacts/regime_gated_pullback_results.json).
