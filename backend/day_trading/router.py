from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .bar_aggregator import SUPPORTED_TIMEFRAMES
from .health import day_trading_runtime
from .models import OrderSide, OrderType, PaperOrderRequest
from .paper_broker import PaperOrderRejected

router = APIRouter(prefix="/day-trading", tags=["day-trading-lab"])


class PaperOrderPayload(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit", "stop"]
    quantity: int = Field(gt=0)
    idempotency_key: str = Field(min_length=8, max_length=128)
    limit_price: float | None = Field(default=None, gt=0)
    stop_price: float | None = Field(default=None, gt=0)
    protective_stop: float | None = Field(default=None, gt=0)


class PaperOrdersToggle(BaseModel):
    enabled: bool


@router.get("/status")
def day_trading_status():
    return day_trading_runtime.status()


@router.get("/market-clock")
def day_trading_market_clock():
    return day_trading_runtime.clock.snapshot()


@router.get("/stream-health")
def day_trading_stream_health():
    return day_trading_runtime.stream.health()


@router.get("/bars/{ticker}")
def day_trading_bars(
    ticker: str,
    timeframe: str = "1m",
):
    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise HTTPException(
            status_code=422,
            detail="Timeframe must be 1m, 5m, or 15m.",
        )
    return day_trading_runtime.ensure_bars(ticker.upper(), timeframe)


@router.get("/quotes/{ticker}")
def day_trading_quotes(ticker: str):
    quote = day_trading_runtime.ensure_quote(ticker.upper())
    if quote is None:
        raise HTTPException(
            status_code=503,
            detail="A current Alpaca quote is not available.",
        )
    return quote


@router.get("/paper-account")
def day_trading_paper_account():
    day_trading_runtime.paper_broker.enforce_no_overnight()
    return day_trading_runtime.paper_broker.account_snapshot()


@router.get("/paper-positions")
def day_trading_paper_positions():
    day_trading_runtime.paper_broker.enforce_no_overnight()
    return day_trading_runtime.paper_broker.positions_snapshot()


@router.post("/paper-orders")
def day_trading_paper_order(payload: PaperOrderPayload):
    try:
        order = day_trading_runtime.paper_broker.submit(
            PaperOrderRequest(
                ticker=payload.ticker,
                side=OrderSide(payload.side),
                order_type=OrderType(payload.order_type),
                quantity=payload.quantity,
                idempotency_key=payload.idempotency_key,
                limit_price=payload.limit_price,
                stop_price=payload.stop_price,
                protective_stop=payload.protective_stop,
            )
        )
        return order.serialize()
    except PaperOrderRejected as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.delete("/paper-orders/{order_id}")
def cancel_day_trading_paper_order(order_id: str):
    try:
        return day_trading_runtime.paper_broker.cancel(order_id).serialize()
    except PaperOrderRejected as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/paper-orders/emergency")
def toggle_day_trading_paper_orders(payload: PaperOrdersToggle):
    return day_trading_runtime.paper_broker.set_orders_enabled(payload.enabled)
