# Pullback Strategy Robustness Test

## Scope

This is an experiment only. It does not change production scoring, thresholds, trade plans, or frontend behavior.

The test used 110 liquid US stocks (ten names from each of the eleven GICS sectors), five years of validated daily Yahoo Finance data, and 52,425 possible EMA20-pullback signal dates. Signals were still calculated after each close using the unchanged institutional analysis. Each configuration waits one, three, or five sessions for the signal-time EMA20 limit, uses a 20-session swing-low stop at 0.5, 1.0, or 1.5 ATR below the low, and rejects risk above 5% of entry.

The 81 fixed combinations cover three target profiles and current, double, and triple slippage plus transaction costs. All use conservative stop-first OHLC handling, no simultaneous positions per ticker, a 30-session maximum hold, and correctly account for partial exits. The detailed configuration, sector, regime, period, and rejection results are in [pullback_robustness_results.json](/Users/beaudidier/Desktop/BEAU-AI-TRADER/artifacts/pullback_robustness_results.json); every completed exit leg is in [pullback_robustness_trades.csv](/Users/beaudidier/Desktop/BEAU-AI-TRADER/artifacts/pullback_robustness_trades.csv).

Market regimes are reporting classifications, not a production change: Bull means SPY close and SMA50 are above SMA200; Bear means both are below; all other dates are Sideways. The data is separated into three chronological, equal-signal-count walk-forward periods.

## Core results

The exact Milestone 28-style configuration (three-day wait, 1 ATR stop, 1.5R/3R targets, current costs) produced 1,176 trades: 0.0739R expectancy, 1.1435 profit factor, 45.32% win rate, -36.4450R maximum drawdown, 413.01 trades/year, and a 95% bootstrap expectancy interval of 0.0030R to 0.1423R.

The strongest broad configuration was three-day wait, 1.5 ATR stop, 2R/4R targets, and current costs:

| Trades | Expectancy / average R | 95% CI | Profit factor | Win rate | Max drawdown | Trades/year |
| ---: | ---: | --- | ---: | ---: | ---: | ---: |
| 605 | 0.1600R | 0.0593R to 0.2619R | 1.3290 | 46.78% | -13.4342R | 364.65 |

The closely related five-day configuration was similar: 624 trades, 0.1624R expectancy, 1.3389 PF, 47.28% win rate, -14.9175R drawdown, and a 0.0663R to 0.2596R interval. This similarity across three- and five-day waits is useful evidence against a single precisely tuned entry window.

## Sensitivity

Average expectancy across the full grid by individual setting was:

| Setting | Result |
| --- | ---: |
| Wait 1 / 3 / 5 sessions | 0.0493R / 0.0554R / 0.0558R |
| Stop 0.5 / 1.0 / 1.5 ATR | 0.0303R / 0.0401R / 0.0902R |
| 1.5R/3R / 2R/4R / full exit 2R | 0.0444R / 0.0728R / 0.0433R |
| Current / double / triple costs | 0.1025R / 0.0504R / 0.0078R |

Costs materially weaken the strongest three-day, 1.5-ATR, 2R/4R plan, but do not fully erase its point estimate:

| Cost level | Trades | Expectancy | 95% CI | PF | Max drawdown |
| --- | ---: | ---: | --- | ---: | ---: |
| Current | 605 | 0.1600R | 0.0593R to 0.2619R | 1.3290 | -13.4342R |
| Double | 575 | 0.1021R | -0.0038R to 0.2070R | 1.1997 | -16.2417R |
| Triple | 555 | 0.0735R | -0.0362R to 0.1817R | 1.1398 | -19.9651R |

The 1.5-ATR stop and 2R/4R targets are the best average settings in this grid, but the 243-way search itself creates parameter-selection risk. This is a robustness study, not confirmation that the best in-sample grid cell will remain best live.

## Sector, regime, and walk-forward dependence

For the strongest three-day configuration, sector results are mixed. Communication Services leads with 43 trades and 0.4429R expectancy; Real Estate follows with 52 trades and 0.3151R. Consumer Discretionary is negative (-0.0917R, 42 trades) and Industrials is approximately flat (-0.0085R, 51 trades). No single sector contributes a majority of positive aggregate expectancy, but many sector intervals cross zero: Energy has only 19 trades, Technology 30, and several other sector samples remain too small for reliable ranking.

| Regime | Trades | Expectancy | 95% CI | PF | Max drawdown |
| --- | ---: | ---: | --- | ---: | ---: |
| Bull | 527 | 0.2348R | 0.1215R to 0.3483R | 1.5047 | -13.4342R |
| Bear | 44 | -0.7680R | -0.9104R to -0.6104R | 0.0540 | -33.7937R |
| Sideways | 34 | 0.2029R | -0.1763R to 0.6010R | 1.5113 | -5.3075R |

| Walk-forward period | Trades | Expectancy | 95% CI | PF |
| --- | ---: | ---: | --- | ---: |
| 1 | 147 | -0.2763R | -0.4469R to -0.0978R | 0.5576 |
| 2 | 286 | 0.3867R | 0.2321R to 0.5412R | 1.9039 |
| 3 | 172 | 0.1561R | -0.0284R to 0.3509R | 1.3349 |

## Findings and recommendation

- **Parameter overfitting risk:** present. The better settings form a small neighbourhood (1.5-ATR stops and either 1.5R/3R, 2R/4R, or full-2R targets), rather than one isolated cell, but the 81-combination grid still requires a future locked-down test.
- **Sector dependence:** not dominated by one sector, but individual-sector estimates are frequently underpowered and several confidence intervals include zero.
- **Regime dependence:** severe. The strategy is strongly positive in Bull periods and clearly negative in Bear periods. This is the most important failure mode.
- **Cost sensitivity:** the selected plan retains PF above one under double costs, satisfying that gate, but its double-cost confidence interval includes zero and drawdown worsens.
- **Sample size:** overall samples are adequate (555–1,176 trades for the highlighted plans), but Bear, Sideways, and several sectors are not. The 44 Bear trades are nevertheless consistently negative enough to be a material warning.

Do **not** promote the Pullback plan to production execution yet. It is suitable for a future controlled paper-trading or locked walk-forward validation only. It passes several requested robustness gates—positive expectancy in two of three chronological periods, PF above one at double costs, diversified sector contribution, and hundreds of trades—but it fails the practical safety test of regime robustness: the Bear result is sharply negative and the first walk-forward period is also negative. A market-regime entry constraint is a hypothesis for a separate experiment, not an implementation recommendation from this audit.
