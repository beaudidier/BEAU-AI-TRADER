import math
from datetime import date

import pandas as pd

from decision_rules import is_actionable_score
from .execution import TP1_PORTION, entry_fill_price, exit_fill_price, transaction_cost
from .report import build_report
from .strategy import build_trade_signal

SLIPPAGE_BPS = 5
TRANSACTION_COST_BPS = 5


def _date_value(timestamp) -> str:
    return pd.Timestamp(timestamp).strftime("%Y-%m-%d")


def _realize_exit(active: dict, cash: float, shares: int, reference_price: float, exit_date: str, reason: str) -> float:
    exit_price = exit_fill_price(reference_price, SLIPPAGE_BPS)
    allocated_entry_cost = active["entry_cost"] * shares / active["shares"]
    exit_cost = transaction_cost(exit_price, shares, TRANSACTION_COST_BPS)
    pnl = (exit_price - active["entry"]) * shares - allocated_entry_cost - exit_cost
    cash += shares * exit_price - exit_cost
    active["remaining_shares"] -= shares
    active["realized_pnl"] += pnl
    active["exit_legs"].append({"reason": reason, "shares": shares, "exit": round(exit_price, 2), "pnl": round(pnl, 2), "date": exit_date})
    return cash


def _close_trade(active: dict, cash: float, reference_price: float, exit_date: str, reason: str) -> tuple[dict, float]:
    cash = _realize_exit(active, cash, active["remaining_shares"], reference_price, exit_date, reason)
    realized_rr = active["realized_pnl"] / active["initial_risk"] if active["initial_risk"] > 0 else 0
    trade = {
        "ticker": active["ticker"],
        "entry_date": active["entry_date"],
        "exit_date": exit_date,
        "entry": round(active["entry"], 2),
        "exit": active["exit_legs"][-1]["exit"],
        "stop_loss": round(active["stop_loss"], 2),
        "target_1": round(active["target_1"], 2),
        "target_2": round(active["target_2"], 2),
        "shares": active["shares"],
        "pnl": round(active["realized_pnl"], 2),
        "realized_rr": round(realized_rr, 2),
        "confidence_score": active["confidence_score"],
        "recommendation": active["recommendation"],
        "exit_reason": reason,
        "exit_legs": active["exit_legs"],
    }
    return trade, cash


def run_backtest(
    ticker: str,
    data: pd.DataFrame,
    start_date: date,
    end_date: date,
    minimum_confidence: int,
    account_size: float,
    risk_percent: float,
) -> dict:
    """Run a one-position-at-a-time, next-candle execution simulation."""

    cash = float(account_size)
    active = None
    trades = []
    equity_curve = []

    for index in range(200, len(data)):
        candle = data.iloc[index]
        candle_date = pd.Timestamp(data.index[index]).date()
        if candle_date < start_date or candle_date > end_date:
            continue

        date_label = _date_value(data.index[index])
        high = float(candle["High"])
        low = float(candle["Low"])
        close = float(candle["Close"])

        if active is not None:
            if low <= active["stop_loss"]:
                trade, cash = _close_trade(active, cash, active["stop_loss"], date_label, "Stop loss")
                trades.append(trade)
                active = None
            else:
                if not active["target_1_hit"] and high >= active["target_1"]:
                    partial_shares = max(1, math.floor(active["shares"] * TP1_PORTION))
                    partial_shares = min(partial_shares, active["remaining_shares"])
                    cash = _realize_exit(active, cash, partial_shares, active["target_1"], date_label, "Target 1")
                    active["target_1_hit"] = True

                if active is not None and high >= active["target_2"]:
                    trade, cash = _close_trade(active, cash, active["target_2"], date_label, "Target 2")
                    trades.append(trade)
                    active = None

        if active is None:
            history = data.iloc[:index]
            plan = build_trade_signal(ticker, history, cash, risk_percent)
            if plan and is_actionable_score(plan["confidence_score"]) and plan["confidence_score"] >= minimum_confidence:
                entry = entry_fill_price(plan["entry"], SLIPPAGE_BPS)
                shares = plan["position_size"]
                if shares > 0 and low <= entry <= high:
                    entry_cost = transaction_cost(entry, shares, TRANSACTION_COST_BPS)
                    cash -= shares * entry + entry_cost
                    active = {
                        "ticker": ticker.upper(), "entry_date": date_label, "entry": entry,
                        "stop_loss": plan["stop_loss"], "target_1": plan["target_1"], "target_2": plan["target_2"],
                        "shares": shares, "remaining_shares": shares, "realized_pnl": 0.0, "entry_cost": entry_cost, "exit_legs": [],
                        "initial_risk": (entry - plan["stop_loss"]) * shares, "target_1_hit": False,
                        "confidence_score": plan["confidence_score"], "recommendation": plan["recommendation"],
                    }

        equity = cash + (active["remaining_shares"] * close if active is not None else 0)
        equity_curve.append({"time": date_label, "value": round(equity, 2)})

    if active is not None and equity_curve:
        final_candle = data.loc[:end_date.isoformat()].iloc[-1]
        final_date = _date_value(final_candle.name)
        trade, cash = _close_trade(active, cash, float(final_candle["Close"]), final_date, "End of test")
        trades.append(trade)
        equity_curve[-1]["value"] = round(cash, 2)

    return build_report(trades, equity_curve, float(account_size))
