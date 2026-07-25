"""Shared, deterministic long-trade execution accounting.

The calibration audit and API backtest use the same 50/50 TP1 rule: sell the
first half at TP1 and retain the remainder with the original stop. Slippage is
adverse on every fill and transaction costs are charged on every entry/exit
leg.
"""

from __future__ import annotations

import math

import pandas as pd

TP1_PORTION = 0.5


def entry_fill_price(raw_open: float, slippage_bps: float) -> float:
    """Return an adverse long entry fill."""
    return float(raw_open) * (1 + float(slippage_bps) / 10_000)


def exit_fill_price(reference_price: float, slippage_bps: float) -> float:
    """Return an adverse long exit fill for a stop, target, or time exit."""
    return float(reference_price) * (1 - float(slippage_bps) / 10_000)


def transaction_cost(price: float, shares: int, transaction_cost_bps: float) -> float:
    return float(price) * int(shares) * float(transaction_cost_bps) / 10_000


def simulate_long_trade(
    data: pd.DataFrame,
    entry_index: int,
    entry_price: float,
    stop_price: float,
    target_1: float,
    target_2: float,
    *,
    shares: int = 100,
    max_holding_days: int = 30,
    slippage_bps: float = 5,
    transaction_cost_bps: float = 5,
) -> dict | None:
    """Simulate a long trade and return aggregate plus separately realized legs.

    The caller supplies an already-slipped entry fill. On a candle that touches
    both a stop and target, the stop is processed first. TP1 sells the
    configured portion; the original stop stays in force for the remainder.
    """
    shares = int(shares)
    if shares <= 0 or entry_price <= stop_price or stop_price <= 0:
        return None

    initial_risk = (entry_price - stop_price) * shares
    if initial_risk <= 0:
        return None

    entry_cost = transaction_cost(entry_price, shares, transaction_cost_bps)
    remaining = shares
    tp1_hit = tp2_hit = stop_hit = False
    high_seen = low_seen = entry_price
    legs: list[dict] = []

    def close_leg(quantity: int, reference_price: float, index: int, reason: str) -> None:
        fill = exit_fill_price(reference_price, slippage_bps)
        allocated_entry_cost = entry_cost * quantity / shares
        exit_cost = transaction_cost(fill, quantity, transaction_cost_bps)
        gross_pnl = (fill - entry_price) * quantity
        pnl = gross_pnl - allocated_entry_cost - exit_cost
        legs.append({
            "leg": reason,
            "shares": quantity,
            "exit_price": fill,
            "exit_index": index,
            "exit_date": str(pd.Timestamp(data.index[index]).date()),
            "gross_pnl": gross_pnl,
            "allocated_entry_cost": allocated_entry_cost,
            "exit_transaction_cost": exit_cost,
            "pnl": pnl,
            "r_multiple": pnl / initial_risk,
        })

    last_index = entry_index
    for index in range(entry_index, min(len(data), entry_index + max_holding_days)):
        candle = data.iloc[index]
        low, high = float(candle["Low"]), float(candle["High"])
        high_seen, low_seen = max(high_seen, high), min(low_seen, low)
        last_index = index

        # Conservative daily-OHLC rule: stops execute before either target.
        if low <= stop_price:
            close_leg(remaining, stop_price, index, "STOP")
            remaining = 0
            stop_hit = True
            break

        if not tp1_hit and high >= target_1:
            quantity = min(remaining, max(1, math.floor(shares * TP1_PORTION)))
            close_leg(quantity, target_1, index, "TP1")
            remaining -= quantity
            tp1_hit = True

        if remaining and high >= target_2:
            close_leg(remaining, target_2, index, "TP2")
            remaining = 0
            tp2_hit = True
            break

    if remaining:
        close_leg(remaining, float(data.iloc[last_index]["Close"]), last_index, "TIME")

    total_pnl = sum(leg["pnl"] for leg in legs)
    total_cost = entry_cost + sum(leg["exit_transaction_cost"] for leg in legs)
    final_leg = legs[-1]
    return {
        "tp1_hit": tp1_hit,
        "tp2_hit": tp2_hit,
        "stop_hit": stop_hit,
        "entry_price": entry_price,
        "entry_transaction_cost": entry_cost,
        "exit_price": final_leg["exit_price"],
        "exit_index": final_leg["exit_index"],
        "holding_days": final_leg["exit_index"] - entry_index + 1,
        "total_pnl": total_pnl,
        "total_transaction_cost": total_cost,
        "return_pct": total_pnl / (entry_price * shares) * 100,
        "r_multiple": total_pnl / initial_risk,
        "mfe_r": (high_seen - entry_price) / (entry_price - stop_price),
        "mae_r": (low_seen - entry_price) / (entry_price - stop_price),
        "exit_legs": legs,
    }
