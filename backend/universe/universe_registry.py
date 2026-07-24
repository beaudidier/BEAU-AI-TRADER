from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from atr import add_atr
from indicators import add_indicators
from providers import get_market_data_provider
from scoring import calculate_score
from volume import add_volume_analysis

from .crypto_universe import CryptoUniverseProvider
from .stock_universe import StockUniverseProvider


PROVIDERS = {"stocks": StockUniverseProvider(), "crypto": CryptoUniverseProvider()}


def universe_symbols(market: str, universe: str, custom_symbols: list[str] | None = None) -> list[str]:
    provider = PROVIDERS.get(market)
    if provider is None or universe not in provider.supported_universes():
        raise ValueError("Unsupported market or universe")
    symbols = provider.symbols(universe, custom_symbols)
    if not symbols:
        raise ValueError("This universe has no symbols")
    return symbols


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scan_symbol(symbol: str) -> dict[str, Any]:
    data = get_market_data_provider().get_history(symbol, period="6mo", interval="1d")
    if data is None or len(data) < 2:
        raise ValueError("No usable market history")
    enriched = add_volume_analysis(add_atr(add_indicators(data)))
    score = calculate_score(enriched)
    current = enriched.iloc[-1]
    return {"ticker": symbol, "price": round(float(current["Close"]), 2), "ema20": round(float(current["EMA20"]), 2), "ema50": round(float(current["EMA50"]), 2), "rsi": round(float(current["RSI"]), 2), "atr": round(float(current["ATR"]), 2), "support": score["support"], "resistance": score["resistance"], "score": score["score"], "recommendation": score["recommendation"], "reasons": score["reasons"], "explanation": score["explanation"]}


@dataclass
class ScanJob:
    job_id: str
    market: str
    universe: str
    symbols: list[str]
    status: str = "queued"
    completed_symbols: int = 0
    failed_symbols: int = 0
    started_at: str | None = None
    completed_at: str | None = None
    results: list[dict[str, Any]] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        total = len(self.symbols)
        return {"job_id": self.job_id, "status": self.status, "market": self.market, "universe": self.universe, "total_symbols": total, "completed_symbols": self.completed_symbols, "failed_symbols": self.failed_symbols, "progress_percentage": round(((self.completed_symbols + self.failed_symbols) / total) * 100, 1) if total else 100, "started_at": self.started_at, "completed_at": self.completed_at}


class ScanJobRegistry:
    def __init__(self, batch_size: int = 10, concurrency_limit: int = 4, symbol_timeout: float = 20, retries: int = 1, cache_seconds: int = 300):
        self.batch_size, self.concurrency_limit, self.symbol_timeout, self.retries, self.cache_seconds = batch_size, concurrency_limit, symbol_timeout, retries, cache_seconds
        self.jobs: dict[str, ScanJob] = {}
        self.cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self.active: dict[str, str] = {}
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="market-scan")

    def start(self, market: str, universe: str, custom_symbols: list[str] | None = None) -> ScanJob:
        symbols = universe_symbols(market, universe, custom_symbols)
        key = f"{market}:{universe}:{','.join(symbols)}"
        with self.lock:
            cached = self.cache.get(key)
            if cached and time.monotonic() - cached[0] < self.cache_seconds:
                job = ScanJob(job_id=str(uuid.uuid4()), market=market, universe=universe, symbols=symbols, status="completed", completed_symbols=len(cached[1]), started_at=_now(), completed_at=_now(), results=cached[1].copy())
                self.jobs[job.job_id] = job
                return job
            active_id = self.active.get(key)
            if active_id and self.jobs[active_id].status in {"queued", "running"}:
                return self.jobs[active_id]
            job = ScanJob(job_id=str(uuid.uuid4()), market=market, universe=universe, symbols=symbols)
            self.jobs[job.job_id] = job
            self.active[key] = job.job_id
        self.executor.submit(self._run, job, key)
        return job

    def _attempt(self, symbol: str) -> dict[str, Any]:
        error: Exception | None = None
        for _ in range(self.retries + 1):
            try:
                return _scan_symbol(symbol)
            except Exception as exc:
                error = exc
        raise error or ValueError("Scan failed")

    def _run(self, job: ScanJob, key: str) -> None:
        job.status, job.started_at = "running", _now()
        try:
            for start in range(0, len(job.symbols), self.batch_size):
                batch = job.symbols[start:start + self.batch_size]
                with ThreadPoolExecutor(max_workers=self.concurrency_limit) as pool:
                    futures = {pool.submit(self._attempt, symbol): symbol for symbol in batch}
                    for future, symbol in futures.items():
                        try:
                            job.results.append(future.result(timeout=self.symbol_timeout))
                            job.completed_symbols += 1
                        except Exception:
                            job.failed_symbols += 1
                            job.failures.append(symbol)
            job.results.sort(key=lambda item: item["score"], reverse=True)
            job.status = "completed"
            with self.lock:
                self.cache[key] = (time.monotonic(), job.results.copy())
        finally:
            job.completed_at = _now()
            with self.lock:
                self.active.pop(key, None)

    def get(self, job_id: str) -> ScanJob | None:
        return self.jobs.get(job_id)


scan_jobs = ScanJobRegistry()
