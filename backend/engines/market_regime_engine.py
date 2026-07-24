import pandas as pd

from .engine_utils import has_valid_market_data


def analyze_market_regime(benchmark_df: pd.DataFrame | None, fallback_df: pd.DataFrame) -> dict:
    """Classify broad market regime using benchmark EMA alignment."""

    data = benchmark_df if benchmark_df is not None and has_valid_market_data(benchmark_df, minimum_rows=200) else fallback_df
    if not has_valid_market_data(data, minimum_rows=50):
        return {"score": 50, "explanation": "Insufficient data to identify market regime.", "confidence": 0}

    close = pd.to_numeric(data["Close"], errors="coerce").dropna()
    ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
    ema200 = close.ewm(span=200, adjust=False).mean().iloc[-1]
    price = close.iloc[-1]
    score = 90 if price > ema50 > ema200 else 65 if price > ema50 else 35 if price > ema200 else 15
    source = "benchmark" if data is benchmark_df else "stock fallback"
    regime = "risk-on" if score >= 65 else "defensive"
    return {"score": score, "explanation": f"The {source} regime is {regime} based on 50/200-day EMA alignment.", "confidence": 100 if source == "benchmark" else 55}
