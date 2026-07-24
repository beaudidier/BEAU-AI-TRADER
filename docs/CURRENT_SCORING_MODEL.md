# Current Scoring Model

This document describes the code as it exists. A confidence score is a deterministic model score from 0 to 100; it is **not** a probability or a percentage chance of profit.

## Recommendation mapping

`backend/decision_rules.py` applies the sole recommendation mapping after the institutional weighted score is rounded and clamped to 0–100:

| Score | Recommendation |
| --- | --- |
| 0–59 | SKIP |
| 60–74 | WATCH |
| 75–89 | BUY |
| 90–100 | STRONG BUY |

## Data source and common behavior

- Provider: `YahooFinanceProvider` through the `MarketDataProvider` interface and `yfinance.download`.
- Institutional analysis endpoint: requests `2y`, `1d` data for the ticker and SPY benchmark.
- The provider uses `auto_adjust=True` and returns OHLCV data. The scoring code uses the final row returned by Yahoo without removing a partial current-day candle. Therefore the latest incomplete daily candle is included whenever Yahoo returns it.
- A valid market row requires finite Open, High, Low, Close, and Volume. Engines return a neutral score of 50 with zero data confidence when their own minimum history/data check fails, except where noted below.
- Weights are loaded from `backend/institutional_weights.json`, normalized to sum to 100% (invalid or unreadable configuration falls back to the defaults).

## Institutional weighted score

`overall_score = clamp(round(sum(engine_score × normalized_weight)))`.

| Engine | Weight |
| --- | ---: |
| Trend | 25% |
| Momentum | 15% |
| Volume | 15% |
| Support/resistance | 15% |
| Volatility | 10% |
| Relative strength | 10% |
| Market regime | 10% |

## Trend engine

- Inputs: adjusted daily Close; EMA20, EMA50, EMA200.
- Formula: +30 if EMA20 > EMA50, otherwise +15; +25 if EMA50 > EMA200, otherwise +10; +25 if Close > EMA20; +10 if Close > EMA50; +10 if Close > EMA200. Clamp 0–100.
- Boundaries: this additive formula produces the score; there are no extra buckets.
- Missing data: invalid latest market row or no usable Close returns 50, data confidence 0. Data confidence is 100 with at least 200 closes, otherwise 60.
- Timeframe/latest candle: all returned daily closes through the latest returned candle.

## Momentum engine

- Inputs: daily Close, RSI(14), MACD default parameters from `ta.trend.MACD` (26/12/9).
- RSI score: 50 for 55–70; 40 for 50–55 or >70–75; 25 for 45–50; otherwise 10.
- MACD score: 50 when MACD > signal and MACD > 0; 30 when MACD > signal or MACD > 0; otherwise 10. Final score is the sum, clamped 0–100.
- Missing data: fewer than 35 valid rows or unavailable indicators returns 50, data confidence 0. Data confidence is 100 at 50+ closes, otherwise 65.
- Timeframe/latest candle: daily through latest returned candle.

## Volume engine

- Inputs: daily Volume and rolling SMA20 of Volume, including the current row.
- Formula: relative volume = current Volume / SMA20. Score: ≥1.5 = 100; ≥1.2 = 85; ≥1.0 = 70; ≥0.8 = 45; otherwise 20.
- Missing data: fewer than 20 valid rows, non-finite volume, or non-positive SMA20 returns 50, data confidence 0. Otherwise confidence is 100.
- Timeframe/latest candle: daily through latest returned candle.

## Support/resistance engine

- Inputs: latest Close plus support = minimum Low and resistance = maximum High across the trailing 20 rows, including latest row.
- Formula: downside = Close − support; upside = resistance − Close; R = upside/downside. Score: R≥3 = 100; ≥2 = 85; ≥1.5 = 70; ≥1 = 50; otherwise 25. If Close is outside the range, score is 20.
- Missing data: fewer than 20 valid rows or invalid levels returns 50, data confidence 0. Otherwise confidence is 100.
- Timeframe/latest candle: daily through latest returned candle.

## Volatility engine

- Inputs: daily High, Low, Close; ATR(14) from `ta.volatility.average_true_range`.
- Formula: ATR% = ATR14 / Close × 100. Score: 1–5% = 90; <1% = 60; >5–8% = 70; >8–12% = 40; >12% = 20.
- Missing data: fewer than 14 valid rows or unavailable ATR/price returns 50, data confidence 0. Otherwise confidence is 100.
- Timeframe/latest candle: daily through latest returned candle.

## Relative-strength engine

- Inputs: ticker 60-session Close return and, when valid, SPY 60-session Close return.
- Formula: stock return = `(Close[t] / Close[t-60] − 1) × 100`; relative return = stock return − benchmark return; score = clamp(round(50 + 2 × relative return)). Without a valid benchmark, benchmark return is 0.
- Boundaries: linear formula clamped to 0–100.
- Missing data: fewer than 60 valid ticker rows returns 50, data confidence 0. A missing/invalid benchmark does not block calculation; it yields confidence 60 rather than 100.
- Timeframe/latest candle: daily through latest returned candle.

## Market-regime engine

- Inputs: SPY daily Close when it has 200 valid rows; otherwise ticker fallback. EMA50 and EMA200 are calculated from Close.
- Formula: score 90 if Close > EMA50 > EMA200; 65 if Close > EMA50; 35 if Close > EMA200; otherwise 15.
- Missing data: fewer than 50 valid rows in the selected source returns 50, data confidence 0. Benchmark source confidence is 100; ticker fallback confidence is 55.
- Timeframe/latest candle: daily through latest returned candle.

## Trade-plan relationship

The trade plan does not recalculate an alternative recommendation. It calls the same decision-rule mapping using its supplied confidence score. It calculates ATR(14), 20-row support/resistance, an entry, stop, targets, and risk/reward for trade sizing; those values can block paper trading but do not alter the decision-rule thresholds.

## Debugging

`GET /debug/score/{ticker}` exposes the exact provider, data timestamp, request timeframe, raw indicator values, engine outputs, normalized weights, weighted contributions, final score/recommendation, invalid values, and differences from the prior debug call for that ticker.
