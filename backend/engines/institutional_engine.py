import json
from pathlib import Path

import pandas as pd

from decision_rules import recommendation_for_score
from .engine_utils import clamp_score
from .explainability_engine import build_explanation
from .market_regime_engine import analyze_market_regime
from .momentum_engine import analyze_momentum
from .relative_strength_engine import analyze_relative_strength
from .support_resistance_engine import analyze_support_resistance
from .trend_engine import analyze_trend
from .volatility_engine import analyze_volatility
from .volume_engine import analyze_volume


WEIGHTS_FILE = Path(__file__).resolve().parent.parent / "institutional_weights.json"
DEFAULT_WEIGHTS = {
    "trend": 25,
    "momentum": 15,
    "volume": 15,
    "support_resistance": 15,
    "volatility": 10,
    "relative_strength": 10,
    "market_regime": 10,
}


def load_weights() -> dict[str, float]:
    """Load editable institutional weights and normalize them to one."""

    try:
        configured = json.loads(WEIGHTS_FILE.read_text())
        weights = {name: float(configured[name]) for name in DEFAULT_WEIGHTS}
        total = sum(weights.values())
        if total <= 0 or any(weight < 0 for weight in weights.values()):
            raise ValueError("Weights must be non-negative with a positive total")
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        weights = DEFAULT_WEIGHTS.copy()
        total = sum(weights.values())

    return {name: weight / total for name, weight in weights.items()}


def calculate_institutional_analysis(df: pd.DataFrame, benchmark_df: pd.DataFrame | None = None) -> dict:
    """Combine seven explainable factors into an institutional analysis result."""

    engines = {
        "trend": analyze_trend(df),
        "momentum": analyze_momentum(df),
        "volume": analyze_volume(df),
        "support_resistance": analyze_support_resistance(df),
        "volatility": analyze_volatility(df),
        "relative_strength": analyze_relative_strength(df, benchmark_df),
        "market_regime": analyze_market_regime(benchmark_df, df),
    }
    weights = load_weights()
    overall_score = clamp_score(sum(engines[name]["score"] * weights[name] for name in weights))

    recommendation = recommendation_for_score(overall_score)

    strengths = [name.replace("_", " ").title() for name, result in engines.items() if result["score"] >= 70]
    weaknesses = [name.replace("_", " ").title() for name, result in engines.items() if result["score"] <= 45]
    warnings = [f"Low data confidence for {name.replace('_', ' ')}." for name, result in engines.items() if result["confidence"] < 60]

    return {
        "overall_score": overall_score,
        "recommendation": recommendation,
        "engines": engines,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "warnings": warnings,
        "explanation": build_explanation(overall_score, engines=engines),
    }
