from .metrics import calculate_metrics


def build_report(trades: list[dict], equity_curve: list[dict], starting_equity: float) -> dict:
    """Format a simulation result into the public API response shape."""

    return {
        "summary": calculate_metrics(trades, equity_curve, starting_equity),
        "equity_curve": equity_curve,
        "trades": trades,
    }
