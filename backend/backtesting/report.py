from .metrics import calculate_metrics


def build_report(trades: list[dict], equity_curve: list[dict], starting_equity: float) -> dict:
    """Format a simulation result into the public API response shape."""

    by_time = {str(point["time"]): point for point in equity_curve}
    chronological_curve = [by_time[timestamp] for timestamp in sorted(by_time)]
    return {
        "summary": calculate_metrics(
            trades, chronological_curve, starting_equity
        ),
        "equity_curve": chronological_curve,
        "trades": trades,
    }
