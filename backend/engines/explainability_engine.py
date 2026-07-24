"""Deterministic, trader-focused explanations for existing model decisions."""

from __future__ import annotations

from typing import Any

from decision_rules import next_threshold_for_score, normalized_score, recommendation_for_score
from .engine_utils import safe_float


def _money(value: Any) -> str | None:
    number = safe_float(value)
    return f"${number:.2f}" if number is not None and number > 0 else None


def _engine_items(engines: dict[str, Any] | None) -> list[tuple[str, dict[str, Any]]]:
    return sorted((engines or {}).items(), key=lambda item: safe_float(item[1].get("score")) or 0, reverse=True)


def build_explanation(
    score: Any,
    *,
    engines: dict[str, Any] | None = None,
    price: Any = None,
    ema20: Any = None,
    ema50: Any = None,
    support: Any = None,
    resistance: Any = None,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Explain a canonical recommendation from the values already calculated."""

    confidence = normalized_score(score)
    verdict = recommendation_for_score(confidence)
    factors = _engine_items(engines)
    strengths = []
    weaknesses = []
    for name, result in factors[:2]:
        factor_score = normalized_score(result.get("score"))
        explanation = str(result.get("explanation") or "").strip()
        if factor_score >= 60:
            strengths.append(f"{name.replace('_', ' ').title()} is supportive at {factor_score}/100" + (f": {explanation}" if explanation else "."))
    for name, result in reversed(factors[-2:]):
        factor_score = normalized_score(result.get("score"))
        explanation = str(result.get("explanation") or "").strip()
        if factor_score < 60:
            weaknesses.append(f"{name.replace('_', ' ').title()} is holding the setup back at {factor_score}/100" + (f": {explanation}" if explanation else "."))

    current_price = _money(price if price is not None else (plan or {}).get("current_price"))
    support_level = _money(support if support is not None else (plan or {}).get("stop_loss"))
    resistance_level = _money(resistance if resistance is not None else (plan or {}).get("target_1"))
    ema20_value = safe_float(ema20)
    ema50_value = safe_float(ema50)
    raw_price = safe_float(price if price is not None else (plan or {}).get("current_price"))

    if not strengths and raw_price and ema20_value:
        strengths.append(f"Price is {'above' if raw_price > ema20_value else 'below'} the 20-day EMA ({_money(ema20_value)}), which is the immediate momentum reference.")
    if not weaknesses and raw_price and ema50_value:
        weaknesses.append(f"Price is {'below' if raw_price < ema50_value else 'near'} the 50-day EMA ({_money(ema50_value)}), so trend follow-through still needs confirmation.")

    risks = []
    rr = safe_float((plan or {}).get("risk_reward_target_1"))
    if rr is not None:
        if not strengths and rr >= 1.5:
            strengths.append(f"The first target offers {rr:.2f}R, providing more planned reward than the risk to the stop.")
        if rr < 1.5:
            risks.append(f"Target 1 offers only {rr:.2f}R, below the 1.5R minimum for a paper entry.")
        else:
            risks.append(f"The planned first target is {rr:.2f}R away; price must reach {resistance_level or 'the first target'} before that reward is realized.")
    elif support_level and resistance_level:
        risks.append(f"The trade is exposed if price loses {support_level} before it can test {resistance_level}.")
    if not risks:
        risks.append("The weakest scored model factor is the main risk until its underlying price and volume conditions improve.")
    if not weaknesses and support_level:
        weaknesses.append(f"The setup depends on support holding at {support_level}; a break there removes the planned risk boundary.")

    next_tier = next_threshold_for_score(confidence)
    if next_tier:
        threshold, label = next_tier
        next_trigger = f"Confidence needs {threshold - confidence} more point{'s' if threshold - confidence != 1 else ''} to reach {label}."
    else:
        next_trigger = "Maintain the current factor strength; the setup is already in the highest confidence tier."
    if raw_price and ema20_value and raw_price <= ema20_value:
        next_trigger += f" A sustained move back above the 20-day EMA at {_money(ema20_value)} would improve momentum."
    elif raw_price and resistance_level:
        next_trigger += f" A decisive move through {resistance_level} with confirmation would strengthen the case."

    invalidation = f"A move below {support_level} invalidates the planned long entry." if support_level else "A break below the nearest validated support invalidates the long thesis."
    if raw_price and ema50_value and raw_price > ema50_value:
        invalidation += f" A sustained loss of the 50-day EMA at {_money(ema50_value)} would also weaken the trend case."

    summary = f"{verdict}: confidence is {confidence}/100. "
    if strengths:
        summary += strengths[0]
    elif weaknesses:
        summary += weaknesses[0]
    else:
        summary += "The available market data does not yet show a decisive edge."

    return {
        "verdict": verdict,
        "summary": summary,
        "strengths": strengths or ["No model factor is currently providing a clear advantage."],
        "weaknesses": weaknesses or ["No material model weakness was identified in the available inputs."],
        "risks": risks,
        "invalidation": invalidation,
        "next_trigger": next_trigger,
        "confidence_explanation": f"{verdict} is assigned directly from the {confidence}/100 confidence score.",
    }
