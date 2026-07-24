import pandas as pd

from .engine_utils import clamp_score, has_valid_market_data, safe_float


def analyze_relative_strength(df: pd.DataFrame, benchmark_df: pd.DataFrame | None = None) -> dict:
    """Compare 60-session performance with a benchmark when it is available."""

    if not has_valid_market_data(df, minimum_rows=60):
        return {"score": 50, "explanation": "Insufficient price history for relative strength.", "confidence": 0}

    stock_return = ((float(df["Close"].iloc[-1]) / float(df["Close"].iloc[-60])) - 1) * 100
    benchmark_return = 0.0
    confidence = 60
    if benchmark_df is not None and has_valid_market_data(benchmark_df, minimum_rows=60):
        benchmark_return = ((float(benchmark_df["Close"].iloc[-1]) / float(benchmark_df["Close"].iloc[-60])) - 1) * 100
        confidence = 100

    relative_return = stock_return - benchmark_return
    score = clamp_score(50 + (relative_return * 2))
    comparison = "the benchmark" if confidence == 100 else "its 60-session baseline"
    return {"score": score, "explanation": f"Relative return is {relative_return:.2f}% versus {comparison}.", "confidence": confidence}
