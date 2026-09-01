from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .bar_aggregator import SUPPORTED_TIMEFRAMES
from .health import day_trading_runtime
from .models import OrderSide, OrderType, PaperOrderRequest
from .paper_broker import PaperOrderRejected

router = APIRouter(prefix="/day-trading", tags=["day-trading-lab"])


def _require_research_mode() -> None:
    if not day_trading_runtime.research_enabled:
        raise HTTPException(
            status_code=404,
            detail="The day-trading research lab is disabled.",
        )


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


class RecordStartPayload(BaseModel):
    symbols: list[str] | None = None


class ReplayStartPayload(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    speed: Literal["original", "10x", "maximum"] = "maximum"


class ReplaySeekPayload(BaseModel):
    timestamp: datetime


class ReplayOrderPayload(BaseModel):
    symbol: str = Field(min_length=1, max_length=10)
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit", "stop"]
    quantity: float = Field(gt=0)
    limit_price: float | None = Field(default=None, gt=0)
    stop_price: float | None = Field(default=None, gt=0)


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


@router.post("/record/start")
def start_day_trading_recording(payload: RecordStartPayload):
    _require_research_mode()
    try:
        symbols = payload.symbols or day_trading_runtime.stream.symbols
        unavailable = sorted(
            set(symbol.upper() for symbol in symbols)
            - set(day_trading_runtime.stream.symbols)
        )
        if unavailable:
            raise ValueError(
                "Recording symbols must already be subscribed to the live stream."
            )
        day_trading_runtime.recorder.start(
            symbols=symbols,
            source=f"Alpaca {day_trading_runtime.stream.feed.upper()}",
            coverage=(
                "partial-market"
                if day_trading_runtime.stream.feed == "iex"
                else "full-market"
            ),
        )
        day_trading_runtime.recorder.record_system(
            "stream_health",
            day_trading_runtime.stream.health(),
        )
        day_trading_runtime.recorder.record_system(
            "market_clock",
            day_trading_runtime.clock.snapshot(),
        )
        return day_trading_runtime.recorder.status()
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/record/stop")
def stop_day_trading_recording():
    _require_research_mode()
    day_trading_runtime.recorder.record_system(
        "stream_health",
        day_trading_runtime.stream.health(),
    )
    day_trading_runtime.recorder.record_system(
        "market_clock",
        day_trading_runtime.clock.snapshot(),
    )
    return day_trading_runtime.recorder.stop()


@router.get("/record/status")
def day_trading_recording_status():
    _require_research_mode()
    return day_trading_runtime.recorder.status()


@router.get("/record/sessions")
def day_trading_recording_sessions():
    _require_research_mode()
    return {"sessions": day_trading_runtime.recorder.sessions()}


@router.post("/replay/start")
def start_day_trading_replay(payload: ReplayStartPayload):
    _require_research_mode()
    try:
        return day_trading_runtime.replay.start(
            payload.session_id,
            speed=payload.speed,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/replay/pause")
def pause_day_trading_replay():
    _require_research_mode()
    return day_trading_runtime.replay.pause()


@router.post("/replay/resume")
def resume_day_trading_replay():
    _require_research_mode()
    return day_trading_runtime.replay.resume()


@router.post("/replay/seek")
def seek_day_trading_replay(payload: ReplaySeekPayload):
    _require_research_mode()
    return day_trading_runtime.replay.seek(payload.timestamp)


@router.post("/replay/reset")
def reset_day_trading_replay():
    _require_research_mode()
    return day_trading_runtime.replay.reset()


@router.get("/replay/status")
def day_trading_replay_status():
    _require_research_mode()
    return day_trading_runtime.replay.status()


@router.get("/replay/bars/{ticker}")
def day_trading_replay_bars(
    ticker: str,
    timeframe: str = "1m",
):
    _require_research_mode()
    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise HTTPException(
            status_code=422,
            detail="Timeframe must be 1m, 5m, or 15m.",
        )
    return day_trading_runtime.replay.aggregator.serialized(
        ticker.upper(),
        timeframe,
    )


@router.get("/replay/verify/{session_id}")
def verify_day_trading_replay(session_id: str):
    _require_research_mode()
    try:
        return {
            "recording": day_trading_runtime.recorder.verify(session_id),
            "determinism": (
                day_trading_runtime.replay.verify_determinism(
                    session_id,
                    runs=3,
                )
            ),
            "bars": day_trading_runtime.replay.verify_bars(session_id),
        }
    except (FileNotFoundError, OSError, ValueError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/replay/orders")
def submit_day_trading_replay_order(payload: ReplayOrderPayload):
    _require_research_mode()
    current = day_trading_runtime.replay.current_timestamp
    if current is None:
        raise HTTPException(
            status_code=409,
            detail="Start or seek a replay before submitting a simulated order.",
        )
    return day_trading_runtime.replay.execution.submit(
        symbol=payload.symbol,
        side=payload.side,
        order_type=payload.order_type,
        quantity=payload.quantity,
        submitted_at=current,
        limit_price=payload.limit_price,
        stop_price=payload.stop_price,
    )


@router.delete("/replay/orders/{order_id}")
def cancel_day_trading_replay_order(order_id: str):
    _require_research_mode()
    try:
        return day_trading_runtime.replay.execution.cancel(order_id)
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail="Replay order was not found.",
        ) from error
