# AI Decision Engine Calibration Audit

## Executive verdict

The full recalibration completed with 30/30 validated liquid US symbols and SPY. It uses the existing scoring, weights, thresholds, and next-open signal process unchanged. The execution accounting is now corrected: a TP1 hit realizes 50% of the position immediately and the remaining 50% retains the original stop until TP2, stop, or the 30-session time exit.

The corrected results still do not justify treating confidence as a probability or changing decision thresholds. BUY has stronger hit rates than WATCH, but its out-of-sample expectancy is only **0.0122R** and its bootstrap interval includes zero. SKIP remains non-monotonic, and there are no STRONG BUY observations.

## Dataset and execution controls

- Explicit range: 2023-07-16 through 2026-07-25 (end exclusive), daily Yahoo Finance OHLCV.
- Validation: every symbol and SPY had at least 600 valid candles, required OHLCV columns, chronological unique dates, positive numeric values, and no incomplete final candle. There were no provider failures.
- Split: chronological 70% calibration / 30% out-of-sample by generated trade; no random shuffle.
- Signal timing: indicators and plans use data through the signal close; entry occurs at the next daily open.
- Costs: every entry and exit leg applies 5 bps adverse slippage and 5 bps transaction cost.
- Partial exits: TP1 closes 50% of initial shares. The original stop remains on the remaining shares. A candle touching both stop and target is resolved as stop first.
- Trade ledger: `artifacts/ai_calibration_trades.csv` stores one row per realized exit leg, linked by `trade_id`.

Artifacts: [results JSON](../artifacts/ai_calibration_results.json), [exit-leg ledger](../artifacts/ai_calibration_trades.csv), and [integrity results](../artifacts/backtest_integrity_results.json).

## Corrected out-of-sample results

The corrected out-of-sample sample contains 300 trades and 502 separately recorded exit legs. TP1 hit rate was **67.33%**, TP2 hit rate **50.33%**, stop-loss rate **25.00%**, win rate **61.67%**, average return **0.3396%**, average R and expectancy **0.1215R**, profit factor **1.4490**, maximum drawdown **-14.1255R**, and average holding time **15.63 days**.

| Band | Trades | TP1 | TP2 | Stop | Win rate | Avg return | Avg R / expectancy | Profit factor | Maximum drawdown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0–59 / SKIP | 72 | 36.11% | 29.17% | 41.67% | 52.78% | 2.5393% | 0.5631R | 2.2401 | -5.2576R |
| 60–74 / WATCH | 128 | 64.06% | 43.75% | 27.34% | 57.03% | -0.4866% | -0.0415R | 0.8575 | -15.0853R |
| 75–89 / BUY | 100 | 94.00% | 74.00% | 10.00% | 74.00% | -0.1867% | 0.0122R | 1.1091 | -2.1934R |
| 90–100 / STRONG BUY | 0 | — | — | — | — | — | — | — | — |

## What changed after partial-exit correction

The comparison uses the previous committed out-of-sample artifact against the corrected exit-leg rerun. Signal count and target/stop hit rates are unchanged; only execution, per-leg costs, realized P/L, and derived metrics changed.

| Scope | Metric | Previous | Corrected | Change |
| --- | --- | ---: | ---: | ---: |
| Overall | Win rate | 62.00% | 61.67% | -0.33 pp |
| Overall | Average return | 0.5422% | 0.3396% | -0.2026 pp |
| Overall | Average R / expectancy | 0.1455R | 0.1215R | -0.0240R |
| Overall | Profit factor | 1.4691 | 1.4490 | -0.0201 |
| Overall | Maximum drawdown | -15.2058R | -14.1255R | +1.0803R |
| SKIP | Average R | 0.6346R | 0.5631R | -0.0715R |
| WATCH | Average R | -0.0439R | -0.0415R | +0.0024R |
| BUY | Average R | 0.0359R | 0.0122R | -0.0237R |
| BUY | Win rate | 76.00% | 74.00% | -2.00 pp |

The correction resolves the prior mismatch between a TP1 flag and realized P/L: all 202 OOS TP1 hits now have a TP1 exit leg. A TP1 trade can still finish non-positive when the target lies at or below the next-open fill or the remaining half loses enough at the original stop/time exit; that is now represented by the sum of the two legs rather than by ignoring TP1 proceeds.

## Integrity findings

- All **999 / 999** ledger trades reproduce from the cached raw OHLCV data, with **0** replay failures.
- All **300 / 300** corrected OOS trades reproduce exactly.
- There are **0** duplicate or overlapping same-ticker positions and **0** incomplete positions counted.
- The 300 OOS trades have 502 exit legs: 202 TP1 legs plus their remaining-position legs, and one-leg direct stop/time exits.
- The reported maximum drawdown is still a sequential R-series drawdown, not a capital-constrained multi-ticker portfolio equity curve.

## Limitations and threshold decision

- No STRONG BUY trade exists in the out-of-sample period.
- BUY’s 0.0122R expectancy is economically small and its 95% bootstrap interval is -0.0520R to 0.0714R.
- WATCH’s 95% expectancy interval is -0.1739R to 0.0971R; neither WATCH nor BUY establishes a stable positive edge.
- SKIP’s positive result is non-monotonic and not actionable evidence.
- The 30-stock current universe retains survivorship bias; liquidity, spread variation, gap fills, and historical index membership remain unmodelled.

No scoring rules, confidence thresholds, factor weights, or signal-generation logic were changed.
