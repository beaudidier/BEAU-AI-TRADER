from datetime import date

from fastapi import HTTPException, status


PLAN_DEFINITIONS = {
    "FREE": {"scans_daily": 10, "watchlists": 1, "saved_analyses": 5, "backtests_monthly": 3, "trade_plan": False},
    "PRO": {"scans_daily": None, "watchlists": 10, "saved_analyses": 100, "backtests_monthly": 50, "trade_plan": True},
    "ELITE": {"scans_daily": None, "watchlists": None, "saved_analyses": None, "backtests_monthly": None, "trade_plan": True},
}


def entitlement_for(plan: str | None) -> dict:
    return PLAN_DEFINITIONS.get(plan or "FREE", PLAN_DEFINITIONS["FREE"])


def require_limit(current: int, limit: int | None, resource: str) -> None:
    if limit is not None and current >= limit:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"{resource} limit reached for the current plan")


def billing_period_start(metric: str, today: date | None = None) -> date:
    today = today or date.today()
    return today if metric == "scans_daily" else today.replace(day=1)
