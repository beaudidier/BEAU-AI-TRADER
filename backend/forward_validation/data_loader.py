"""Bounded, resumable market-data loading for forward validation."""

from __future__ import annotations

import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

import pandas as pd

from engines.engine_utils import REQUIRED_MARKET_COLUMNS, safe_float
from .health import classify_data_error, symbol_outcome

HistoryFetcher = Callable[[str], pd.DataFrame | None]
BatchHistoryFetcher = Callable[[list[str]], dict[str, pd.DataFrame]]
CheckpointCallback = Callable[[dict[str, object]], None]


def _positive_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _non_negative_float(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if math.isfinite(value) and value >= 0 else default


@dataclass(frozen=True)
class LoaderConfig:
    batch_size: int = 20
    concurrency_limit: int = 2
    symbol_timeout_seconds: float = 30.0
    max_retries: int = 2
    initial_backoff_seconds: float = 0.5
    request_pacing_seconds: float = 0.15
    maximum_workflow_seconds: float = 1_380.0
    cache_dir: Path = Path("artifacts/forward_validation_cache")

    @classmethod
    def from_environment(cls) -> "LoaderConfig":
        return cls(
            batch_size=_positive_int("FORWARD_VALIDATION_BATCH_SIZE", 20),
            concurrency_limit=_positive_int("FORWARD_VALIDATION_CONCURRENCY_LIMIT", 2),
            symbol_timeout_seconds=_non_negative_float(
                "FORWARD_VALIDATION_SYMBOL_TIMEOUT_SECONDS", 30.0
            ),
            max_retries=_positive_int(
                "FORWARD_VALIDATION_MAX_RETRIES", 2, minimum=0
            ),
            initial_backoff_seconds=_non_negative_float(
                "FORWARD_VALIDATION_INITIAL_BACKOFF_SECONDS", 0.5
            ),
            request_pacing_seconds=_non_negative_float(
                "FORWARD_VALIDATION_REQUEST_PACING_SECONDS", 0.15
            ),
            maximum_workflow_seconds=_non_negative_float(
                "FORWARD_VALIDATION_MAX_WORKFLOW_SECONDS", 1_380.0
            ),
            cache_dir=Path(
                os.getenv(
                    "FORWARD_VALIDATION_CACHE_DIR",
                    "artifacts/forward_validation_cache",
                )
            ),
        )


@dataclass
class LoadResult:
    histories: dict[str, pd.DataFrame]
    failed_symbols: list[str]
    provider_errors: dict[str, str]
    symbol_outcomes: dict[str, dict[str, str]]
    cached_symbols: list[str]
    provider_request_count: int
    retry_count: int
    batches_completed: int
    total_batches: int
    duplicate_requests_prevented: int
    workflow_timed_out: bool
    runtime_seconds: float


def validate_completed_history(
    history: pd.DataFrame | None,
    expected_session: date,
) -> pd.DataFrame:
    if history is None or history.empty:
        raise ValueError("No completed daily history was returned.")
    if any(column not in history.columns for column in REQUIRED_MARKET_COLUMNS):
        missing = [
            column for column in REQUIRED_MARKET_COLUMNS if column not in history.columns
        ]
        raise ValueError(f"Required OHLCV fields are missing: {', '.join(missing)}.")

    result = history.copy()
    result.index = pd.to_datetime(result.index).tz_localize(None)
    if result.index.has_duplicates:
        raise ValueError("Historical data contains duplicate market dates.")
    if not result.index.is_monotonic_increasing:
        raise ValueError("Historical data is not in chronological order.")

    valid_rows = result.loc[:, list(REQUIRED_MARKET_COLUMNS)].apply(
        lambda column: column.map(lambda value: safe_float(value) is not None)
    ).all(axis=1)
    result = result.loc[valid_rows]
    if result.empty:
        raise ValueError("No complete OHLCV candles were available.")

    latest_session = pd.Timestamp(result.index[-1]).date()
    if latest_session < expected_session:
        raise ValueError(
            f"Stale market data: latest completed candle is {latest_session.isoformat()}, "
            f"expected {expected_session.isoformat()}."
        )
    if latest_session > expected_session:
        result = result.loc[result.index.date <= expected_session]
        if result.empty or pd.Timestamp(result.index[-1]).date() != expected_session:
            raise ValueError(
                f"Market history does not contain the required session "
                f"{expected_session.isoformat()}."
            )
    return result


class ForwardValidationDataLoader:
    """Load one immutable completed session with bounded provider pressure."""

    def __init__(
        self,
        fetcher: HistoryFetcher,
        expected_session: date,
        *,
        batch_fetcher: BatchHistoryFetcher | None = None,
        config: LoaderConfig | None = None,
        checkpoint: CheckpointCallback | None = None,
    ) -> None:
        self.fetcher = fetcher
        self.batch_fetcher = batch_fetcher
        self.expected_session = expected_session
        self.config = config or LoaderConfig.from_environment()
        self.checkpoint = checkpoint
        self.provider_request_count = 0
        self.retry_count = 0
        self._request_lock = threading.Lock()
        self._next_request_at = 0.0

    def _cache_path(self, symbol: str) -> Path:
        safe_symbol = "".join(
            character if character.isalnum() or character in {"-", "."} else "_"
            for character in symbol.upper()
        )
        return (
            self.config.cache_dir
            / self.expected_session.isoformat()
            / f"{safe_symbol}.csv"
        )

    def _read_cache(self, symbol: str) -> pd.DataFrame | None:
        path = self._cache_path(symbol)
        if not path.exists():
            return None
        try:
            history = pd.read_csv(path, index_col=0, parse_dates=True)
            return validate_completed_history(history, self.expected_session)
        except (OSError, ValueError, pd.errors.ParserError):
            return None

    def _write_cache(self, symbol: str, history: pd.DataFrame) -> None:
        path = self._cache_path(symbol)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".csv.tmp")
        history.to_csv(temporary)
        temporary.replace(path)

    def _paced_fetch(self, symbol: str) -> pd.DataFrame | None:
        with self._request_lock:
            now = time.monotonic()
            delay = max(0.0, self._next_request_at - now)
            if delay:
                time.sleep(delay)
            self._next_request_at = (
                time.monotonic() + self.config.request_pacing_seconds
            )
            self.provider_request_count += 1
        return self.fetcher(symbol)

    def _paced_batch_fetch(
        self, symbols: list[str]
    ) -> dict[str, pd.DataFrame]:
        if self.batch_fetcher is None:
            return {}
        with self._request_lock:
            now = time.monotonic()
            delay = max(0.0, self._next_request_at - now)
            if delay:
                time.sleep(delay)
            self._next_request_at = (
                time.monotonic() + self.config.request_pacing_seconds
            )
            self.provider_request_count += 1
        return self.batch_fetcher(symbols)

    def _fetch_with_retry(self, symbol: str) -> pd.DataFrame:
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            if attempt:
                self.retry_count += 1
                time.sleep(
                    self.config.initial_backoff_seconds * (2 ** (attempt - 1))
                )
            try:
                history = self._paced_fetch(symbol)
                validated = validate_completed_history(
                    history, self.expected_session
                )
                self._write_cache(symbol, validated)
                return validated
            except Exception as error:
                last_error = error
        raise last_error or ValueError("Market-data request failed.")

    def _fetch_batch_with_retry(
        self, symbols: list[str]
    ) -> dict[str, pd.DataFrame]:
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            if attempt:
                self.retry_count += 1
                time.sleep(
                    self.config.initial_backoff_seconds * (2 ** (attempt - 1))
                )
            try:
                return self._paced_batch_fetch(symbols)
            except Exception as error:
                last_error = error
        raise last_error or ValueError("Batch market-data request failed.")

    def _load_individual_fallback(
        self,
        symbols: list[str],
        histories: dict[str, pd.DataFrame],
        failed: list[str],
        errors: dict[str, str],
    ) -> None:
        if not symbols:
            return
        executor = ThreadPoolExecutor(
            max_workers=self.config.concurrency_limit,
            thread_name_prefix="forward-validation-retry",
        )
        futures = {
            symbol: executor.submit(self._fetch_with_retry, symbol)
            for symbol in symbols
        }
        for symbol, future in futures.items():
            try:
                histories[symbol] = future.result(
                    timeout=self.config.symbol_timeout_seconds
                )
                errors.pop(symbol, None)
            except FutureTimeoutError:
                failed.append(symbol)
                errors[symbol] = (
                    f"Market-data request exceeded "
                    f"{self.config.symbol_timeout_seconds:g} seconds."
                )
                future.cancel()
            except Exception as error:
                failed.append(symbol)
                errors[symbol] = str(error) or type(error).__name__
        executor.shutdown(wait=False, cancel_futures=True)

    def load(
        self,
        symbols: list[str],
        *,
        resume_completed: list[str] | None = None,
    ) -> LoadResult:
        started = time.monotonic()
        requested: list[str] = []
        seen: set[str] = set()
        duplicates = 0
        for raw_symbol in symbols:
            symbol = str(raw_symbol).strip().upper()
            if not symbol:
                continue
            if symbol in seen:
                duplicates += 1
                continue
            seen.add(symbol)
            requested.append(symbol)

        histories: dict[str, pd.DataFrame] = {}
        cached_symbols: list[str] = []
        failed: list[str] = []
        errors: dict[str, str] = {}
        resume = set(resume_completed or [])
        pending: list[str] = []
        for symbol in requested:
            cached = self._read_cache(symbol)
            if cached is not None:
                histories[symbol] = cached
                cached_symbols.append(symbol)
            else:
                pending.append(symbol)
                if symbol in resume:
                    errors[symbol] = (
                        "Checkpoint existed but its completed-data cache was unavailable; "
                        "the provider request was resumed."
                    )

        batches = [
            pending[start : start + self.config.batch_size]
            for start in range(0, len(pending), self.config.batch_size)
        ]
        completed_batches = 0
        workflow_timed_out = False
        for batch_index, batch in enumerate(batches):
            elapsed = time.monotonic() - started
            if (
                self.config.maximum_workflow_seconds > 0
                and elapsed >= self.config.maximum_workflow_seconds
            ):
                workflow_timed_out = True
                for symbol in pending[batch_index * self.config.batch_size :]:
                    if symbol not in failed:
                        failed.append(symbol)
                        errors[symbol] = "Maximum workflow duration was reached."
                break

            if self.batch_fetcher is not None:
                batch_executor = ThreadPoolExecutor(
                    max_workers=1,
                    thread_name_prefix="forward-validation-batch",
                )
                future = batch_executor.submit(
                    self._fetch_batch_with_retry, batch
                )
                try:
                    batch_histories = future.result(
                        timeout=self.config.symbol_timeout_seconds
                    )
                except FutureTimeoutError:
                    batch_histories = {}
                    for symbol in batch:
                        errors[symbol] = (
                            f"Batch market-data request exceeded "
                            f"{self.config.symbol_timeout_seconds:g} seconds."
                        )
                    future.cancel()
                except Exception as error:
                    batch_histories = {}
                    for symbol in batch:
                        errors[symbol] = str(error) or type(error).__name__
                batch_executor.shutdown(wait=False, cancel_futures=True)

                missing = []
                for symbol in batch:
                    try:
                        history = validate_completed_history(
                            batch_histories.get(symbol),
                            self.expected_session,
                        )
                        histories[symbol] = history
                        self._write_cache(symbol, history)
                        errors.pop(symbol, None)
                    except Exception as error:
                        errors[symbol] = str(error) or type(error).__name__
                        missing.append(symbol)
                self._load_individual_fallback(
                    missing, histories, failed, errors
                )
            else:
                self._load_individual_fallback(
                    batch, histories, failed, errors
                )
            completed_batches += 1
            if self.checkpoint is not None:
                self.checkpoint(
                    {
                        "batch_index": batch_index + 1,
                        "batches_completed": completed_batches,
                        "total_batches": len(batches),
                        "symbols_completed": sorted(histories),
                        "symbols_failed": sorted(set(failed)),
                        "cached_symbols": sorted(cached_symbols),
                        "provider_request_count": self.provider_request_count,
                        "retry_count": self.retry_count,
                        "runtime_seconds": round(time.monotonic() - started, 3),
                    }
                )

        return LoadResult(
            histories=histories,
            failed_symbols=sorted(set(failed)),
            provider_errors=errors,
            symbol_outcomes={
                symbol: (
                    symbol_outcome(
                        "completed",
                        "Completed daily OHLCV data passed all loader quality gates.",
                    )
                    if symbol in histories
                    else classify_data_error(
                        errors.get(symbol, "Market-data provider did not return data.")
                    )
                )
                for symbol in requested
            },
            cached_symbols=sorted(cached_symbols),
            provider_request_count=self.provider_request_count,
            retry_count=self.retry_count,
            batches_completed=completed_batches,
            total_batches=len(batches),
            duplicate_requests_prevented=duplicates,
            workflow_timed_out=workflow_timed_out,
            runtime_seconds=round(time.monotonic() - started, 3),
        )
