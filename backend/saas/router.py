from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from .auth import CurrentUser, get_current_user, get_user_client
from .entitlements import entitlement_for, require_limit


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


def _data(response): return response.data or []
def _one(response): return response.data or {}
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
