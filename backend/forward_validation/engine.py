"""Frozen, deterministic paper-only forward-validation strategy.

The rules in this module mirror the selected Milestone 30 configuration:
existing market-regime score >= 65, a three-session EMA20 limit, a stop 1.5
ATR below the signal-time 20-session swing low, 2R/4R targets, 50% at TP1,
the original stop for the remainder, and conservative stop-first processing.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from atr import add_atr
from backtesting.execution import entry_fill_price, exit_fill_price, transaction_cost
from engines.engine_utils import has_valid_market_data, safe_float
from engines.institutional_engine import calculate_institutional_analysis

STRATEGY_VERSION = "regime-gated-pullback-v1.0.0"
STRATEGY_METADATA = {
    "name": "Regime-Gated Pullback",
    "status": "Forward Validation",
    "asset_class": "US stocks",
    "trading_style": "Swing Trading",
    "direction": "Long-only",
    "strategy_version": STRATEGY_VERSION,
    "disclaimer": "Forward validation only. Not proven for live-money trading.",
}

ENTRY_WAIT = 3
STOP_ATR = 1.5
TARGET_1_R = 2.0
TARGET_2_R = 4.0
TP1_PORTION = 0.5
SLIPPAGE_BPS = 5.0
TRANSACTION_COST_BPS = 5.0
MAX_HOLDING_DAYS = 30
MAX_RISK_PCT = 0.05
APPROVAL_MIN_TRADES = 100
APPROVAL_MAX_DRAWDOWN_R = -15.0


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def build_live_signal(
    ticker: str,
    history: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    signal_timestamp: str | None = None,
) -> dict[str, Any] | None:
    """Return an immutable signal snapshot, or None when the regime disallows it."""

    if not has_valid_market_data(history, minimum_rows=200) or not has_valid_market_data(benchmark, minimum_rows=200):
        raise ValueError("At least 200 valid daily candles are required.")
    enriched = add_atr(history.copy())
    atr = safe_float(enriched["ATR"].iloc[-1])
    if atr is None or atr <= 0:
        raise ValueError("ATR is unavailable for the frozen strategy.")
    analysis = calculate_institutional_analysis(history, benchmark)
    market = analysis["engines"]["market_regime"]
    if _number(market.get("score")) < 65:
        return None

    close = pd.to_numeric(history["Close"], errors="coerce")
    proposed_entry = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
    expected_fill = entry_fill_price(proposed_entry, SLIPPAGE_BPS)
    swing_low = float(pd.to_numeric(history["Low"], errors="coerce").tail(20).min())
    stop = swing_low - STOP_ATR * atr
    risk = expected_fill - stop
    if stop <= 0 or risk <= 0 or risk / expected_fill > MAX_RISK_PCT:
        return None

    now = signal_timestamp or datetime.now(timezone.utc).isoformat()
    return {
        "ticker": ticker.upper(),
        "signal_timestamp": now,
        "signal_price": round(float(close.iloc[-1]), 6),
        "proposed_pullback_entry": round(proposed_entry, 6),
        "expected_entry_fill": round(expected_fill, 6),
        "stop_loss": round(stop, 6),
        "target_1": round(expected_fill + TARGET_1_R * risk, 6),
        "target_2": round(expected_fill + TARGET_2_R * risk, 6),
        "market_regime": str(market.get("explanation") or "Risk-on"),
        "market_regime_score": round(_number(market.get("score")), 2),
        "confidence": round(_number(analysis.get("overall_score")), 2),
        "strategy_version": STRATEGY_VERSION,
        "data_timestamp": pd.Timestamp(history.index[-1]).isoformat(),
    }


def _replay(signal: dict[str, Any], history: pd.DataFrame, cost_multiplier: int) -> dict[str, Any]:
    data_timestamp = pd.Timestamp(signal["data_timestamp"])
    future = history.loc[history.index > data_timestamp].copy()
    proposed = _number(signal["proposed_pullback_entry"])
    stop = _number(signal["stop_loss"])
    entry = entry_fill_price(proposed, SLIPPAGE_BPS * cost_multiplier)
    risk_per_share = entry - stop
    target_1 = entry + TARGET_1_R * risk_per_share
    target_2 = entry + TARGET_2_R * risk_per_share
    if future.empty:
        return {"status": "ACTIVE", "entry_price": None, "entry_timestamp": None, "completed_at": None, "tp1_hit": False, "tp2_hit": False, "stop_hit": False, "open_pl": 0.0, "realized_r": 0.0, "holding_days": 0, "costs": 0.0, "slippage": 0.0, "remaining_fraction": 1.0}

    entry_position = None
    for position in range(min(ENTRY_WAIT, len(future))):
        candle = future.iloc[position]
        if _number(candle["Low"]) <= proposed <= _number(candle["High"]):
            entry_position = position
            break
    if entry_position is None:
        status = "EXPIRED" if len(future) >= ENTRY_WAIT else "ACTIVE"
        return {"status": status, "entry_price": None, "entry_timestamp": None, "completed_at": future.index[min(len(future), ENTRY_WAIT) - 1].isoformat() if status == "EXPIRED" else None, "tp1_hit": False, "tp2_hit": False, "stop_hit": False, "open_pl": 0.0, "realized_r": 0.0, "holding_days": 0, "costs": 0.0, "slippage": 0.0, "remaining_fraction": 1.0}

    candles = future.iloc[entry_position:]
    entry_cost = transaction_cost(entry, 1, TRANSACTION_COST_BPS * cost_multiplier)
    entry_slippage = entry - proposed
    remaining = 1.0
    realized_r = 0.0
    costs = entry_cost
    slippage = entry_slippage
    tp1_hit = tp2_hit = stop_hit = False
    final_timestamp = None

    def close_leg(fraction: float, reference: float) -> None:
        nonlocal realized_r, costs, slippage
        fill = exit_fill_price(reference, SLIPPAGE_BPS * cost_multiplier)
        exit_cost = transaction_cost(fill, fraction, TRANSACTION_COST_BPS * cost_multiplier)
        allocated_entry_cost = entry_cost * fraction
        pnl = (fill - entry) * fraction - allocated_entry_cost - exit_cost
        realized_r += pnl / risk_per_share
        costs += exit_cost
        slippage += (reference - fill) * fraction

    for offset, (timestamp, candle) in enumerate(candles.iloc[:MAX_HOLDING_DAYS].iterrows(), start=1):
        low, high = _number(candle["Low"]), _number(candle["High"])
        if low <= stop:
            close_leg(remaining, stop)
            remaining = 0.0; stop_hit = True; final_timestamp = timestamp
            break
        if not tp1_hit and high >= target_1:
            close_leg(TP1_PORTION, target_1)
            remaining -= TP1_PORTION; tp1_hit = True
        if remaining and high >= target_2:
            close_leg(remaining, target_2)
            remaining = 0.0; tp2_hit = True; final_timestamp = timestamp
            break
        if offset == MAX_HOLDING_DAYS:
            close_leg(remaining, _number(candle["Close"]))
            remaining = 0.0; final_timestamp = timestamp
            break

    holding_days = min(len(candles), MAX_HOLDING_DAYS)
    if remaining:
        latest = _number(candles.iloc[-1]["Close"])
        open_pl = (latest - entry) * remaining - entry_cost * remaining + realized_r * risk_per_share
        status = "OPEN"
    else:
        open_pl = 0.0
        status = "COMPLETED"
    return {
        "status": status,
        "entry_price": round(entry, 6),
        "entry_timestamp": candles.index[0].isoformat(),
        "completed_at": final_timestamp.isoformat() if final_timestamp is not None else None,
        "tp1_hit": tp1_hit,
        "tp2_hit": tp2_hit,
        "stop_hit": stop_hit,
        "open_pl": round(open_pl, 6),
        "realized_r": round(realized_r, 6),
        "holding_days": holding_days,
        "costs": round(costs, 6),
        "slippage": round(slippage, 6),
        "remaining_fraction": round(remaining, 4),
    }


def evaluate_signal(signal: dict[str, Any], history: pd.DataFrame) -> dict[str, Any]:
    """Replay all completed candles after the immutable signal snapshot."""

    current = _replay(signal, history, 1)
    doubled = _replay(signal, history, 2)
    current["double_cost_realized_r"] = doubled["realized_r"] if doubled["status"] == "COMPLETED" else None
    return current


def build_dashboard(signals: list[dict[str, Any]], outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    outcome_by_signal = {str(item.get("signal_id")): item for item in outcomes}
    combined = [{**signal, "outcome": outcome_by_signal.get(str(signal.get("id")), {"status": "ACTIVE"})} for signal in signals]
    completed = [item for item in combined if item["outcome"].get("status") == "COMPLETED"]
    completed_chronological = sorted(completed, key=lambda item: str(item.get("signal_timestamp") or ""))
    values = [_number(item["outcome"].get("realized_r")) for item in completed_chronological]
    gains = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    equity = peak = drawdown = 0.0
    for value in values:
        equity += value; peak = max(peak, equity); drawdown = min(drawdown, equity - peak)
    double_values = [_number(item["outcome"].get("double_cost_realized_r")) for item in completed_chronological if item["outcome"].get("double_cost_realized_r") is not None]
    double_gains = sum(value for value in double_values if value > 0)
    double_losses = abs(sum(value for value in double_values if value < 0))
    metrics = {
        "expectancy": round(sum(values) / len(values), 4) if values else 0.0,
        "profit_factor": round(gains / losses, 4) if losses else (None if not gains else 999.0),
        "win_rate": round(sum(value > 0 for value in values) / len(values) * 100, 2) if values else 0.0,
        "maximum_drawdown": round(drawdown, 4),
        "total_sample_size": len(values),
        "double_cost_expectancy": round(sum(double_values) / len(double_values), 4) if double_values else 0.0,
        "double_cost_profit_factor": round(double_gains / double_losses, 4) if double_losses else (None if not double_gains else 999.0),
    }
    pf = metrics["profit_factor"] or 0
    double_pf = metrics["double_cost_profit_factor"] or 0
    metrics["approval"] = {
        "minimum_completed_trades": len(values) >= APPROVAL_MIN_TRADES,
        "positive_expectancy": metrics["expectancy"] > 0,
        "profit_factor_above_one": pf > 1,
        "acceptable_drawdown": metrics["maximum_drawdown"] >= APPROVAL_MAX_DRAWDOWN_R,
        "positive_after_double_costs": metrics["double_cost_expectancy"] > 0 and double_pf > 1,
        "approved": len(values) >= APPROVAL_MIN_TRADES and metrics["expectancy"] > 0 and pf > 1 and metrics["maximum_drawdown"] >= APPROVAL_MAX_DRAWDOWN_R and metrics["double_cost_expectancy"] > 0 and double_pf > 1,
    }
    return {
        "strategy": STRATEGY_METADATA,
        "active_signals": [item for item in combined if item["outcome"].get("status") == "ACTIVE"],
        "expired_signals": [item for item in combined if item["outcome"].get("status") == "EXPIRED"],
        "open_paper_trades": [item for item in combined if item["outcome"].get("status") == "OPEN"],
        "completed_trades": completed,
        "metrics": metrics,
    }
