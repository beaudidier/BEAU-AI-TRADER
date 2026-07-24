import pandas as pd

from .momentum_engine import calculate_momentum_score
from .risk_engine import calculate_risk_score
from .structure_engine import calculate_structure_score
from .trend_engine import calculate_trend_score
from .volatility_engine import calculate_volatility_score
from .volume_engine import calculate_volume_score


WEIGHTS = {
    "trend": 0.30,
    "momentum": 0.20,
    "volume": 0.15,
    "structure": 0.20,
    "volatility": 0.05,
    "risk": 0.10,
}


def calculate_confidence(df: pd.DataFrame) -> dict[str, int]:
    """Combine each independent analysis engine into a weighted confidence score."""

    scores = {
        "trend": calculate_trend_score(df),
        "momentum": calculate_momentum_score(df),
        "volume": calculate_volume_score(df),
        "structure": calculate_structure_score(df),
        "volatility": calculate_volatility_score(df),
        "risk": calculate_risk_score(df),
    }
    confidence = round(sum(scores[name] * WEIGHTS[name] for name in WEIGHTS))

    return {"confidence": confidence, **scores}
