import pandas as pd

from .institutional_engine import calculate_institutional_analysis


def calculate_confidence(df: pd.DataFrame) -> dict[str, int]:
    """Compatibility adapter for consumers that need a single confidence value."""

    analysis = calculate_institutional_analysis(df)
    return {
        "confidence": analysis["overall_score"],
        **{name: result["score"] for name, result in analysis["engines"].items()},
    }
