# AI Decision Engine Calibration Audit

## Executable-entry recalibration

Signals remain calculated after the daily close. Each historical plan is recalculated from the next daily open with 5 bps adverse entry slippage before any stop, target, risk, sizing, or R/R calculation. Partial exits remain 50% at TP1 and the original stop remains on the balance.

The audit rejected **12,709** invalid executable-entry attempts: 12,347 moved too far above the original setup, 11,871 had Target 1 R/R below 1.5, 771 had Target 1 at or below entry, 770 opened at or above the original Target 1, and 573 had zero position size. Reasons can overlap. Rejections are retained in `artifacts/ai_calibration_trades.csv` with `record_type=REJECTED`.

## Corrected out-of-sample results

186 accepted trades remained after validation. Overall: 40.86% win rate, 0.9877% average return, 0.2732R expectancy, 1.4633 profit factor, and -26.3098R chronological exit-leg maximum drawdown.

| Band | Trades | TP1 | TP2 | Stop | Win rate | Expectancy / Avg R | Profit factor | Drawdown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SKIP | 76 | 25.00% | 19.74% | 55.26% | 42.11% | 0.4259R | 1.7374 | -16.2608R |
| WATCH | 89 | 31.46% | 15.73% | 53.93% | 42.70% | 0.2197R | 1.3893 | -13.0953R |
| BUY | 21 | 28.57% | 28.57% | 71.43% | 28.57% | -0.0531R | 0.9282 | -6.3877R |
| STRONG BUY | 0 | — | — | — | — | — | — | — |

BUY’s bootstrap expectancy interval is **-0.7070R to 0.6137R**. The executable-entry validation removed the previous apparent BUY advantage; it does not establish a positive BUY edge.

No confidence score, factor weight, threshold, or signal-generation rule changed.
