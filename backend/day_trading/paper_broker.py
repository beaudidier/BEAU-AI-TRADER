from __future__ import annotations

from datetime import date, datetime, timezone
from threading import RLock
from uuid import uuid4

from .market_clock import MarketClock
from .models import (
    ClosedPaperPosition,
    MarketSession,
    OrderSide,
    OrderStatus,
    OrderType,
    PaperOrder,
    PaperOrderRequest,
    PaperPosition,
)
from .quote_cache import QuoteCache
from .session import as_utc
from .session import EASTERN, classify_market_session

MAX_RISK_PER_TRADE_PERCENT = 0.25
MAX_OPEN_DAY_TRADES = 2
MAX_DAILY_LOSS_PERCENT = 0.5


class PaperOrderRejected(ValueError):
    pass


class PaperBroker:
    """In-memory paper execution with atomic risk admission."""

    def __init__(
        self,
        quote_cache: QuoteCache,
        market_clock: MarketClock,
        *,
        starting_balance: float = 100_000,
        max_spread_percent: float = 0.25,
    ):
        if starting_balance <= 0:
            raise ValueError("Starting paper balance must be positive.")
        self.quote_cache = quote_cache
        self.market_clock = market_clock
        self.starting_balance = float(starting_balance)
        self.cash = float(starting_balance)
        self.max_spread_percent = float(max_spread_percent)
        self.orders: dict[str, PaperOrder] = {}
        self.positions: dict[str, PaperPosition] = {}
        self.closed_positions: list[ClosedPaperPosition] = []
        self._idempotency: dict[str, str] = {}
        self._lock = RLock()
        self._orders_enabled = True
        self._trading_day: date | None = None
        self._day_start_equity = self.starting_balance

    @property
    def orders_enabled(self) -> bool:
        return self._orders_enabled

    def set_orders_enabled(self, enabled: bool) -> dict:
        with self._lock:
            self._orders_enabled = bool(enabled)
        return {
            "paper_orders_enabled": self._orders_enabled,
            "paper_only": True,
        }

    def _refresh_day(self, now: datetime) -> None:
        trading_day = now.astimezone(EASTERN).date()
        if self._trading_day != trading_day:
            self._trading_day = trading_day
            self._day_start_equity = self.equity()

    def equity(self) -> float:
        market_value = sum(
            position.current_price * position.quantity
            for position in self.positions.values()
        )
        return self.cash + market_value

    def daily_pnl(self) -> float:
        return self.equity() - self._day_start_equity

    def daily_loss_locked(self) -> bool:
        return self.daily_pnl() <= -(
            self._day_start_equity * MAX_DAILY_LOSS_PERCENT / 100
        )

    def _open_entry_slots(self) -> int:
        pending_buys = sum(
            1
            for order in self.orders.values()
            if order.status == OrderStatus.PENDING
            and order.request.side == OrderSide.BUY
        )
        return len(self.positions) + pending_buys

    def _validate_entry(
        self,
        request: PaperOrderRequest,
        execution_price: float,
        now: datetime,
        *,
        reserved_order_id: str | None = None,
    ) -> None:
        if self.daily_loss_locked():
            raise PaperOrderRejected(
                "Daily loss limit reached. Paper trading is locked until the next trading day."
            )
        if request.ticker in self.positions or any(
            order.status == OrderStatus.PENDING
            and order.request.ticker == request.ticker
            and order.request.side == OrderSide.BUY
            and order.id != reserved_order_id
            for order in self.orders.values()
        ):
            raise PaperOrderRejected(
                "Averaging down and duplicate ticker entries are disabled."
            )
        reserved_slots = 1 if reserved_order_id else 0
        if self._open_entry_slots() - reserved_slots >= MAX_OPEN_DAY_TRADES:
            raise PaperOrderRejected(
                "Maximum of 2 open day trades has been reached."
            )
        quote = self.quote_cache.get(request.ticker)
        if quote is None or self.quote_cache.is_stale(request.ticker, now=now):
            raise PaperOrderRejected("The quote is stale or unavailable.")
        if quote.spread_percent > self.max_spread_percent:
            raise PaperOrderRejected(
                f"Quote spread exceeds {self.max_spread_percent:.2f}%."
            )
        if request.protective_stop is None:
            raise PaperOrderRejected(
                "A protective stop is required for every paper entry."
            )
        if request.protective_stop <= 0 or request.protective_stop >= execution_price:
            raise PaperOrderRejected(
                "Protective stop must be positive and below the entry price."
            )
        risk = (
            execution_price - request.protective_stop
        ) * request.quantity
        maximum = self.equity() * MAX_RISK_PER_TRADE_PERCENT / 100
        if risk <= 0 or risk > maximum + 1e-9:
            raise PaperOrderRejected(
                "Order risk exceeds the 0.25% paper-account limit."
            )
        if execution_price * request.quantity > self.cash:
            raise PaperOrderRejected("Paper account cash is insufficient.")

    def _execution_reference(self, request: PaperOrderRequest) -> float:
        quote = self.quote_cache.get(request.ticker)
        if quote is None:
            raise PaperOrderRejected("The quote is stale or unavailable.")
        if request.order_type == OrderType.LIMIT:
            if request.limit_price is None or request.limit_price <= 0:
                raise PaperOrderRejected("A valid limit price is required.")
            return request.limit_price
        if request.order_type == OrderType.STOP:
            if request.stop_price is None or request.stop_price <= 0:
                raise PaperOrderRejected("A valid stop trigger is required.")
            return request.stop_price
        return quote.ask if request.side == OrderSide.BUY else quote.bid

    def submit(
        self,
        request: PaperOrderRequest,
        *,
        now: datetime | None = None,
    ) -> PaperOrder:
        current = as_utc(now or self.market_clock.current_time())
        normalized = PaperOrderRequest(
            ticker=request.ticker.strip().upper(),
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            idempotency_key=request.idempotency_key.strip(),
            limit_price=request.limit_price,
            stop_price=request.stop_price,
            protective_stop=request.protective_stop,
        )
        if not normalized.ticker or normalized.quantity <= 0:
            raise PaperOrderRejected("Ticker and positive quantity are required.")
        if not normalized.idempotency_key:
            raise PaperOrderRejected("An idempotency key is required.")
        with self._lock:
            existing_id = self._idempotency.get(normalized.idempotency_key)
            if existing_id:
                existing = self.orders[existing_id]
                if existing.request != normalized:
                    raise PaperOrderRejected(
                        "This idempotency key was already used for another paper order."
                    )
                return existing
            self._refresh_day(current)
            if not self._orders_enabled:
                raise PaperOrderRejected(
                    "Paper orders are disabled by the emergency switch."
                )
            if classify_market_session(current) != MarketSession.REGULAR:
                raise PaperOrderRejected(
                    "Paper orders are allowed only during the regular session."
                )
            quote = self.quote_cache.get(normalized.ticker)
            if quote is None or self.quote_cache.is_stale(
                normalized.ticker,
                now=current,
            ):
                raise PaperOrderRejected("The quote is stale or unavailable.")
            if quote.spread_percent > self.max_spread_percent:
                raise PaperOrderRejected(
                    f"Quote spread exceeds {self.max_spread_percent:.2f}%."
                )
            execution_price = self._execution_reference(normalized)
            if normalized.side == OrderSide.BUY:
                self._validate_entry(normalized, execution_price, current)
            elif normalized.ticker not in self.positions:
                raise PaperOrderRejected(
                    "Short selling is disabled; no long position exists to close."
                )
            elif normalized.quantity > self.positions[normalized.ticker].quantity:
                raise PaperOrderRejected(
                    "Sell quantity exceeds the open paper position."
                )
            order = PaperOrder(
                id=str(uuid4()),
                request=normalized,
                status=OrderStatus.PENDING,
                created_at=current,
                updated_at=current,
            )
            self.orders[order.id] = order
            self._idempotency[normalized.idempotency_key] = order.id
            if self._should_fill(normalized):
                self._fill(order, current)
            return order

    def _should_fill(self, request: PaperOrderRequest) -> bool:
        quote = self.quote_cache.get(request.ticker)
        if quote is None:
            return False
        if request.order_type == OrderType.MARKET:
            return True
        if request.order_type == OrderType.LIMIT:
            return (
                request.limit_price >= quote.ask
                if request.side == OrderSide.BUY
                else request.limit_price <= quote.bid
            )
        return (
            request.stop_price <= quote.ask
            if request.side == OrderSide.BUY
            else request.stop_price >= quote.bid
        )

    def _fill(self, order: PaperOrder, now: datetime) -> None:
        request = order.request
        quote = self.quote_cache.get(request.ticker)
        if quote is None:
            return
        fill_price = quote.ask if request.side == OrderSide.BUY else quote.bid
        if request.side == OrderSide.BUY:
            self.cash -= fill_price * request.quantity
            self.positions[request.ticker] = PaperPosition(
                ticker=request.ticker,
                quantity=request.quantity,
                entry_price=fill_price,
                protective_stop=float(request.protective_stop),
                opened_at=now,
                current_price=quote.midpoint,
            )
        else:
            self._close_position(
                request.ticker,
                min(request.quantity, self.positions[request.ticker].quantity),
                fill_price,
                now,
                "manual paper order",
            )
        order.status = OrderStatus.FILLED
        order.fill_price = fill_price
        order.filled_at = now
        order.updated_at = now

    def process_quote(
        self,
        ticker: str,
        *,
        now: datetime | None = None,
    ) -> None:
        current = as_utc(now or self.market_clock.current_time())
        if classify_market_session(current) != MarketSession.REGULAR:
            self.enforce_no_overnight(now=current)
            return
        symbol = ticker.upper()
        with self._lock:
            quote = self.quote_cache.get(symbol)
            if quote is None:
                return
            position = self.positions.get(symbol)
            if position:
                position.current_price = quote.midpoint
                position.unrealized_pnl = (
                    quote.midpoint - position.entry_price
                ) * position.quantity
                if quote.bid <= position.protective_stop:
                    self._close_position(
                        symbol,
                        position.quantity,
                        quote.bid,
                        current,
                        "protective stop",
                    )
            for order in list(self.orders.values()):
                if (
                    order.status == OrderStatus.PENDING
                    and order.request.ticker == symbol
                    and self._should_fill(order.request)
                ):
                    if order.request.side == OrderSide.BUY:
                        try:
                            self._validate_entry(
                                order.request,
                                quote.ask,
                                current,
                                reserved_order_id=order.id,
                            )
                        except PaperOrderRejected as error:
                            order.status = OrderStatus.REJECTED
                            order.rejection_reason = str(error)
                            order.updated_at = current
                            continue
                    self._fill(order, current)

    def _close_position(
        self,
        ticker: str,
        quantity: int,
        exit_price: float,
        now: datetime,
        reason: str,
    ) -> None:
        position = self.positions[ticker]
        close_quantity = min(quantity, position.quantity)
        self.cash += exit_price * close_quantity
        realized = (exit_price - position.entry_price) * close_quantity
        self.closed_positions.append(
            ClosedPaperPosition(
                ticker=ticker,
                quantity=close_quantity,
                entry_price=position.entry_price,
                exit_price=exit_price,
                opened_at=position.opened_at,
                closed_at=now,
                realized_pnl=realized,
                reason=reason,
            )
        )
        if close_quantity == position.quantity:
            del self.positions[ticker]
        else:
            position.quantity -= close_quantity

    def enforce_no_overnight(
        self,
        *,
        now: datetime | None = None,
    ) -> int:
        current = as_utc(now or self.market_clock.current_time())
        if classify_market_session(current) == MarketSession.REGULAR:
            return 0
        closed = 0
        with self._lock:
            for order in self.orders.values():
                if order.status == OrderStatus.PENDING:
                    order.status = OrderStatus.CANCELLED
                    order.rejection_reason = "Expired at the market close."
                    order.updated_at = current
            for ticker in list(self.positions):
                quote = self.quote_cache.get(ticker)
                position = self.positions[ticker]
                self._close_position(
                    ticker,
                    position.quantity,
                    quote.bid if quote is not None else position.current_price,
                    current,
                    "mandatory market-close flatten",
                )
                closed += 1
        return closed

    def cancel(
        self,
        order_id: str,
        *,
        now: datetime | None = None,
    ) -> PaperOrder:
        current = as_utc(now or self.market_clock.current_time())
        with self._lock:
            order = self.orders.get(order_id)
            if order is None:
                raise PaperOrderRejected("Paper order was not found.")
            if order.status != OrderStatus.PENDING:
                raise PaperOrderRejected(
                    "Only pending paper orders can be cancelled."
                )
            order.status = OrderStatus.CANCELLED
            order.updated_at = current
            return order

    def positions_snapshot(self) -> dict:
        with self._lock:
            return {
                "open": [
                    position.serialize()
                    for position in self.positions.values()
                ],
                "closed": [
                    position.serialize()
                    for position in self.closed_positions[-100:]
                ],
            }

    def account_snapshot(self) -> dict:
        with self._lock:
            equity = self.equity()
            daily_pnl = self.daily_pnl()
            return {
                "starting_balance": round(self.starting_balance, 2),
                "cash": round(self.cash, 2),
                "equity": round(equity, 2),
                "realized_pnl": round(
                    sum(item.realized_pnl for item in self.closed_positions),
                    2,
                ),
                "unrealized_pnl": round(
                    sum(item.unrealized_pnl for item in self.positions.values()),
                    2,
                ),
                "daily_pnl": round(daily_pnl, 2),
                "daily_loss_limit": round(
                    self._day_start_equity * MAX_DAILY_LOSS_PERCENT / 100,
                    2,
                ),
                "daily_loss_locked": self.daily_loss_locked(),
                "paper_orders_enabled": self._orders_enabled,
                "open_positions": len(self.positions),
                "maximum_open_positions": MAX_OPEN_DAY_TRADES,
                "maximum_risk_per_trade_percent": MAX_RISK_PER_TRADE_PERCENT,
                "maximum_daily_loss_percent": MAX_DAILY_LOSS_PERCENT,
                "paper_only": True,
                "live_money_enabled": False,
            }
