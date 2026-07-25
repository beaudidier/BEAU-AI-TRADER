import pandas as pd

from atr import add_atr
from engines.confidence_engine import calculate_confidence
from engines.engine_utils import has_valid_market_data, safe_float
from engines.trade_plan_engine import calculate_trade_plan
from support_resistance import calculate_support_resistance


def build_trade_signal(ticker: str, history: pd.DataFrame, account_size: float, risk_percent: float, executable_entry: float | None = None) -> dict | None:
    """Produce a plan from the prior close, optionally recalculated at the next open."""

    if not has_valid_market_data(history, minimum_rows=200):
        return None

    enriched_history = add_atr(history)
    atr = safe_float(enriched_history["ATR"].iloc[-1])
    if atr is None or atr <= 0:
        return None

    confidence = calculate_confidence(enriched_history)
    levels = calculate_support_resistance(enriched_history)

    try:
        plan = calculate_trade_plan(
            ticker=ticker,
            df=enriched_history,
            account_size=account_size,
            risk_percent=risk_percent,
            confidence_output=confidence,
            support=levels["support"],
            resistance=levels["resistance"],
            atr=atr,
            executable_entry=executable_entry,
        )
    except ValueError:
        return None

    return plan
