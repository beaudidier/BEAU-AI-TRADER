import math
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from .auth import CurrentUser, get_current_user, get_user_client
from .entitlements import entitlement_for, require_limit
from coach.coach_engine import analyze_completed_trade
from paper_trading.engine import build_close_preview, build_portfolio_summary, build_trade_coach_payload
from paper_trading.portfolio_risk import build_portfolio_risk_dashboard
from paper_trading.validation import validate_long_paper_trade
from providers import get_market_data_provider
from engines.institutional_engine import calculate_institutional_analysis
from learning.learning_engine import build_learning_context, build_learning_dashboard, build_learning_trade_update
from forward_validation import build_dashboard as build_forward_validation_dashboard
from forward_validation.setup_clarity import enrich_dashboard
from forward_validation.runner import (
    SupabaseForwardValidationStore,
    run_for_user as run_forward_validation_for_user,
    runner_health,
)


router = APIRouter(prefix="/me", tags=["SaaS user data"])


class ProfileUpdate(BaseModel):
    display_name: str | None = None
    avatar_url: str | None = None
    timezone: str | None = None
    trading_experience: str | None = None
    risk_profile: str | None = None


class SettingsUpdate(BaseModel):
    default_account_size: float | None = Field(default=None, gt=0)
    default_risk_percent: float | None = Field(default=None, gt=0, le=100)
    preferred_currency: str | None = None
    theme: str | None = None


class WatchlistCreate(BaseModel): name: str = Field(min_length=1, max_length=80)
class WatchlistUpdate(WatchlistCreate): pass
class WatchlistItemCreate(BaseModel): ticker: str = Field(min_length=1, max_length=20)
class SavedAnalysisCreate(BaseModel): ticker: str; analysis_json: dict[str, Any]
class BacktestSave(BaseModel): ticker: str; parameters: dict[str, Any]; results: dict[str, Any]
class TradeCreate(BaseModel):
    ticker: str; side: str; entry_price: float; stop_price: float | None = None; target_price: float | None = None; quantity: float; status: str = "OPEN"; notes: str | None = None
class TradeUpdate(BaseModel):
    stop_price: float | None = None; target_price: float | None = None; quantity: float | None = None; status: str | None = None; pnl: float | None = None; notes: str | None = None


class PaperTradeOpen(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    side: Literal["BUY"]
    current_price: float
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    quantity: float
    confidence_score: float
    recommendation: str = Field(min_length=1, max_length=40)
    risk_reward_target_1: float


def _data(response): return response.data or []
def _one(response):
    if response is None:
        return {}
    data = response.data
    if isinstance(data, list):
        return data[0] if data else {}
    return data or {}
def _client(user: CurrentUser): return get_user_client(user)


@router.get("")
def me(user: CurrentUser = Depends(get_current_user)):
    client = _client(user)
    profile = _one(client.table("profiles").select("*").eq("id", user.id).maybe_single().execute())
    subscription = _one(client.table("subscriptions").select("*").eq("user_id", user.id).order("created_at", desc=True).limit(1).maybe_single().execute())
    return {"user": {"id": user.id, "email": user.email}, "profile": profile, "subscription": subscription, "entitlements": entitlement_for(subscription.get("plan"))}


@router.patch("/profile")
def update_profile(payload: ProfileUpdate, user: CurrentUser = Depends(get_current_user)):
    values = {key: value for key, value in payload.model_dump().items() if value is not None}
    return _one(_client(user).table("profiles").update(values).eq("id", user.id).execute())


@router.get("/settings")
def get_settings(user: CurrentUser = Depends(get_current_user)):
    return _one(_client(user).table("user_settings").select("*").eq("user_id", user.id).maybe_single().execute())


@router.patch("/settings")
def update_settings(payload: SettingsUpdate, user: CurrentUser = Depends(get_current_user)):
    values = {key: value for key, value in payload.model_dump().items() if value is not None}
    return _one(_client(user).table("user_settings").update(values).eq("user_id", user.id).execute())


@router.get("/watchlists")
def list_watchlists(user: CurrentUser = Depends(get_current_user)):
    return _data(_client(user).table("watchlists").select("*, watchlist_items(*) ").eq("user_id", user.id).execute())


@router.post("/watchlists", status_code=status.HTTP_201_CREATED)
def create_watchlist(payload: WatchlistCreate, user: CurrentUser = Depends(get_current_user)):
    client = _client(user)
    subscription = _one(client.table("subscriptions").select("plan").eq("user_id", user.id).limit(1).maybe_single().execute())
    count = len(_data(client.table("watchlists").select("id").eq("user_id", user.id).execute()))
    require_limit(count, entitlement_for(subscription.get("plan"))["watchlists"], "Watchlist")
    return _one(client.table("watchlists").insert({"user_id": user.id, "name": payload.name}).execute())


@router.patch("/watchlists/{watchlist_id}")
def update_watchlist(watchlist_id: str, payload: WatchlistUpdate, user: CurrentUser = Depends(get_current_user)):
    return _one(_client(user).table("watchlists").update({"name": payload.name}).eq("id", watchlist_id).execute())


@router.delete("/watchlists/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist(watchlist_id: str, user: CurrentUser = Depends(get_current_user)):
    _client(user).table("watchlists").delete().eq("id", watchlist_id).execute(); return Response(status_code=204)


@router.post("/watchlists/{watchlist_id}/items", status_code=status.HTTP_201_CREATED)
def add_watchlist_item(watchlist_id: str, payload: WatchlistItemCreate, user: CurrentUser = Depends(get_current_user)):
    return _one(_client(user).table("watchlist_items").insert({"watchlist_id": watchlist_id, "ticker": payload.ticker.upper()}).execute())


@router.delete("/watchlists/{watchlist_id}/items/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist_item(watchlist_id: str, ticker: str, user: CurrentUser = Depends(get_current_user)):
    _client(user).table("watchlist_items").delete().eq("watchlist_id", watchlist_id).eq("ticker", ticker.upper()).execute(); return Response(status_code=204)


@router.get("/saved-analyses")
def list_saved_analyses(user: CurrentUser = Depends(get_current_user)):
    return _data(_client(user).table("saved_analyses").select("*").eq("user_id", user.id).order("created_at", desc=True).execute())


@router.post("/saved-analyses", status_code=status.HTTP_201_CREATED)
def save_analysis(payload: SavedAnalysisCreate, user: CurrentUser = Depends(get_current_user)):
    client = _client(user); subscription = _one(client.table("subscriptions").select("plan").eq("user_id", user.id).limit(1).maybe_single().execute())
    count = len(_data(client.table("saved_analyses").select("id").eq("user_id", user.id).execute()))
    require_limit(count, entitlement_for(subscription.get("plan"))["saved_analyses"], "Saved analysis")
    return _one(client.table("saved_analyses").insert({"user_id": user.id, "ticker": payload.ticker.upper(), "analysis_json": payload.analysis_json}).execute())


@router.delete("/saved-analyses/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(analysis_id: str, user: CurrentUser = Depends(get_current_user)):
    _client(user).table("saved_analyses").delete().eq("id", analysis_id).execute(); return Response(status_code=204)


@router.get("/backtests")
def list_backtests(user: CurrentUser = Depends(get_current_user)):
    return _data(_client(user).table("backtest_runs").select("*").eq("user_id", user.id).order("created_at", desc=True).execute())


@router.post("/backtests/save", status_code=status.HTTP_201_CREATED)
def save_backtest(payload: BacktestSave, user: CurrentUser = Depends(get_current_user)):
    client = _client(user); subscription = _one(client.table("subscriptions").select("plan").eq("user_id", user.id).limit(1).maybe_single().execute())
    count = len(_data(client.table("backtest_runs").select("id").eq("user_id", user.id).execute()))
    require_limit(count, entitlement_for(subscription.get("plan"))["backtests_monthly"], "Monthly backtest")
    return _one(client.table("backtest_runs").insert({"user_id": user.id, "ticker": payload.ticker.upper(), "parameters": payload.parameters, "results": payload.results}).execute())


@router.get("/trades")
def list_trades(user: CurrentUser = Depends(get_current_user)):
    return _data(_client(user).table("trades").select("*").eq("user_id", user.id).order("opened_at", desc=True).execute())


@router.post("/trades", status_code=status.HTTP_201_CREATED)
def create_trade(payload: TradeCreate, user: CurrentUser = Depends(get_current_user)):
    values = payload.model_dump(); values.update({"user_id": user.id, "ticker": payload.ticker.upper(), "side": payload.side.upper()})
    return _one(_client(user).table("trades").insert(values).execute())


@router.patch("/trades/{trade_id}")
def update_trade(trade_id: str, payload: TradeUpdate, user: CurrentUser = Depends(get_current_user)):
    values = {key: value for key, value in payload.model_dump().items() if value is not None}
    return _one(_client(user).table("trades").update(values).eq("id", trade_id).execute())


@router.delete("/trades/{trade_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trade(trade_id: str, user: CurrentUser = Depends(get_current_user)):
    _client(user).table("trades").delete().eq("id", trade_id).execute(); return Response(status_code=204)


def _quote_price(ticker: str) -> float:
    quote = get_market_data_provider().get_quote(ticker)
    try:
        price = float((quote or {}).get("price"))
    except (TypeError, ValueError):
        price = 0
    if not math.isfinite(price) or price <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unable to obtain a valid market quote")
    return price


def _learning_context(payload: PaperTradeOpen, recommendation: str) -> dict[str, Any]:
    """Capture explainable setup conditions without blocking paper execution on data gaps."""

    provider = get_market_data_provider()
    try:
        history = provider.get_history(payload.ticker, period="1y", interval="1d")
        benchmark = provider.get_history("SPY", period="1y", interval="1d")
        analysis = calculate_institutional_analysis(history, benchmark) if history is not None else None
        company = provider.get_company(payload.ticker)
    except Exception:
        analysis, company = None, None
    return build_learning_context(payload.ticker, payload.confidence_score, recommendation, analysis, company)


def _forward_validation_store(user: CurrentUser) -> SupabaseForwardValidationStore:
    return SupabaseForwardValidationStore(_client(user))


def _forward_validation_dashboard(store: SupabaseForwardValidationStore, user_id: str) -> dict[str, Any]:
    signals = store.list_signals(user_id)
    outcomes = store.list_outcomes(user_id)
    dashboard = enrich_dashboard(
        build_forward_validation_dashboard(signals, outcomes)
    )
    dashboard["runner"] = runner_health(store.list_runs(user_id))
    completed = dashboard["metrics"]["total_sample_size"]
    dashboard["sample_progress"] = {
        "completed": completed,
        "required": 100,
        "percentage": min(100, round(completed)),
    }
    account = store.get_paper_account(user_id)
    paper_trades = store.list_paper_trades(user_id)
    dashboard["portfolio_risk"] = build_portfolio_risk_dashboard(
        account,
        paper_trades,
    )
    dashboard["portfolio_risk_rejections"] = store.list_risk_rejections(
        user_id
    )
    return dashboard


@router.get("/forward-validation/dashboard")
def get_forward_validation_dashboard(user: CurrentUser = Depends(get_current_user)):
    """Return immutable signals, paper outcomes, and frozen-strategy approval metrics."""

    return _forward_validation_dashboard(_forward_validation_store(user), user.id)


@router.post("/forward-validation/run")
def run_forward_validation(user: CurrentUser = Depends(get_current_user)):
    """Run the frozen paper-only strategy after a completed US market session."""

    store = _forward_validation_store(user)
    try:
        run = run_forward_validation_for_user(store, user.id, trigger="manual")
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Forward validation could not finish. Stored signals and trades remain unchanged.",
        ) from error
    return {"run": run, "dashboard": _forward_validation_dashboard(store, user.id)}


@router.post("/forward-validation/scan")
def scan_forward_validation_signals(user: CurrentUser = Depends(get_current_user)):
    """Compatibility endpoint backed by the automated runner."""

    result = run_forward_validation(user)
    run = result["run"]
    return {
        "created": [],
        "created_count": run.get("signals_created", 0),
        "duplicate_count": run.get("duplicates_prevented", 0),
        "regime_disallowed_count": 0,
        "unavailable_count": len(run.get("symbols_failed") or []),
        "run": run,
    }


@router.post("/forward-validation/refresh")
def refresh_forward_validation(user: CurrentUser = Depends(get_current_user)):
    """Compatibility endpoint that runs outcome evaluation and returns the dashboard."""

    return run_forward_validation(user)["dashboard"]


@router.get("/paper-trading/portfolio")
def get_paper_portfolio(user: CurrentUser = Depends(get_current_user)):
    """Return the authenticated user's simulated account, positions, and performance."""

    client = _client(user)
    account = _one(client.table("paper_accounts").select("*").eq("user_id", user.id).maybe_single().execute())
    if not account:
        account = _one(client.table("paper_accounts").insert({"user_id": user.id}).execute())
    trades = _data(client.table("paper_trades").select("*").eq("user_id", user.id).order("opened_at", desc=True).execute())
    open_trades = [trade for trade in trades if trade.get("status") == "OPEN"]
    closed_trades = [trade for trade in trades if trade.get("status") == "CLOSED"]
    quotes = {ticker: get_market_data_provider().get_quote(ticker) or {} for ticker in {trade["ticker"] for trade in open_trades}}
    portfolio = build_portfolio_summary(
        account, open_trades, closed_trades, quotes
    )
    portfolio["portfolio_risk"] = build_portfolio_risk_dashboard(
        account,
        trades,
        portfolio_balance=portfolio["portfolio_balance"],
    )
    portfolio["risk_rejections"] = _data(
        client.table("portfolio_risk_rejections")
        .select("*")
        .eq("user_id", user.id)
        .order("rejected_at", desc=True)
        .limit(100)
        .execute()
    )
    return portfolio


@router.post("/paper-trading/open", status_code=status.HTTP_201_CREATED)
def open_paper_trade(payload: PaperTradeOpen, user: CurrentUser = Depends(get_current_user)):
    """Open a validated simulated long position using stored trade-plan values."""

    try:
        recommendation = validate_long_paper_trade(payload.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    context = _learning_context(payload, recommendation)
    parameters = {
        "p_ticker": payload.ticker.upper(), "p_side": payload.side, "p_entry_price": payload.entry_price,
        "p_stop_loss": payload.stop_loss, "p_target_1": payload.target_1, "p_target_2": payload.target_2,
        "p_quantity": payload.quantity, "p_confidence_score": payload.confidence_score, "p_recommendation": recommendation,
        "p_setup_quality": context["setup_quality"], "p_market_regime": context["market_regime"], "p_trend": context["trend"], "p_momentum": context["momentum"], "p_sector": context["sector"],
    }
    try:
        result = _one(
            _client(user).rpc("open_paper_trade", parameters).execute()
        )
        if result.get("blocked"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": result.get("rejection_reason")
                    or "This paper trade exceeds the validated portfolio limits.",
                    "capacity_resets_at": result.get("capacity_resets_at"),
                    "limiting_positions": result.get("limiting_positions") or [],
                },
            )
        return result
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unable to open paper trade. Check account balance and trade values.") from error


@router.get("/paper-trading/{trade_id}/close-preview")
def preview_paper_trade_close(trade_id: str, user: CurrentUser = Depends(get_current_user)):
    """Return a non-mutating close estimate using the latest available quote."""

    trade = _one(_client(user).table("paper_trades").select("*").eq("id", trade_id).eq("user_id", user.id).eq("status", "OPEN").maybe_single().execute())
    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Open paper trade not found")
    quote = _quote_price(trade["ticker"])
    return build_close_preview(trade, quote, datetime.now(timezone.utc).isoformat())


@router.post("/paper-trading/{trade_id}/close")
def close_paper_trade(trade_id: str, user: CurrentUser = Depends(get_current_user)):
    """Close an open simulated position at the latest provider quote and run AI Coach."""

    client = _client(user)
    existing = _one(client.table("paper_trades").select("ticker").eq("id", trade_id).eq("user_id", user.id).eq("status", "OPEN").maybe_single().execute())
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Open paper trade not found")
    try:
        trade = _one(client.rpc("close_paper_trade", {"p_trade_id": trade_id, "p_exit_price": _quote_price(existing["ticker"])}).execute())
        coach_analysis = analyze_completed_trade(build_trade_coach_payload(trade))
        learning_update = build_learning_trade_update(trade, coach_analysis)
        updated = _one(client.table("paper_trades").update({"coach_analysis": coach_analysis, **learning_update}).eq("id", trade_id).execute())
        return updated or {**trade, "coach_analysis": coach_analysis}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unable to close paper trade") from error


@router.get("/learning/dashboard")
def get_learning_dashboard(ticker: str | None = Query(default=None, min_length=1, max_length=20), user: CurrentUser = Depends(get_current_user)):
    """Aggregate all completed paper trades into deterministic personal learning insights."""

    query = _client(user).table("paper_trades").select("*").eq("user_id", user.id).eq("status", "CLOSED")
    if ticker:
        query = query.eq("ticker", ticker.upper())
    trades = _data(query.order("closed_at", desc=True).execute())
    return build_learning_dashboard(trades)
