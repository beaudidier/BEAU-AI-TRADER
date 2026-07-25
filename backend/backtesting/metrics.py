def calculate_metrics(trades: list[dict], equity_curve: list[dict], starting_equity: float) -> dict:
    """Calculate portfolio and trade metrics from completed trades."""

    # Multiple updates for one session collapse to the final session value.
    # Sorting by timestamp makes the public backtest independent of caller or
    # ticker iteration order.
    by_time = {str(point["time"]): float(point["value"]) for point in equity_curve}
    chronological_curve = [
        {"time": timestamp, "value": by_time[timestamp]}
        for timestamp in sorted(by_time)
    ]

    total_trades = len(trades)
    wins = sum(1 for trade in trades if trade["pnl"] > 0)
    losses = sum(1 for trade in trades if trade["pnl"] <= 0)
    gross_profit = sum(trade["pnl"] for trade in trades if trade["pnl"] > 0)
    gross_loss = abs(sum(trade["pnl"] for trade in trades if trade["pnl"] < 0))
    average_rr = sum(trade["realized_rr"] for trade in trades) / total_trades if total_trades else 0
    average_confidence = sum(trade["confidence_score"] for trade in trades) / total_trades if total_trades else 0
    expectancy = sum(trade["pnl"] for trade in trades) / total_trades if total_trades else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)

    peak = starting_equity
    max_drawdown = 0.0
    for point in chronological_curve:
        value = point["value"]
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = max(max_drawdown, ((peak - value) / peak) * 100)

    return {
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": round((wins / total_trades) * 100, 2) if total_trades else 0,
        "average_rr": round(average_rr, 2),
        "average_confidence": round(average_confidence, 2),
        "max_drawdown": round(max_drawdown, 2),
        "profit_factor": round(profit_factor, 2),
        "expectancy": round(expectancy, 2),
        "starting_equity": round(starting_equity, 2),
        "ending_equity": round(chronological_curve[-1]["value"] if chronological_curve else starting_equity, 2),
        "net_profit": round((chronological_curve[-1]["value"] if chronological_curve else starting_equity) - starting_equity, 2),
    }
