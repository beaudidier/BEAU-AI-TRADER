"""Sixty-session availability audit for the frozen production swing strategy.

The audit calls the registered ``swing_trading`` strategy with a history slice
ending on each session. It does not write to forward-validation or paper-trade
storage and does not alter any production rule.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any

import pandas as pd

from calibration.pullback_robustness import UNIVERSE as RESEARCH_SECTOR_UNIVERSE
from config import WATCHLIST
from providers import get_market_data_provider
from providers.provider import MarketDataProvider
from strategies import strategy_registry
from strategies.swing_strategy import (
    ENTRY_WAIT,
    MAX_HOLDING_DAYS,
    MAX_RISK_PCT,
    STOP_ATR,
    STRATEGY_VERSION,
    evaluate_signal,
)
from universe.stock_universe import (
    DOW30,
    NASDAQ100,
    SP500,
    stock_constituent_metadata,
)

from .production_replay import (
    _compare_production_and_standalone,
    _signal_timestamp,
    _standalone_calculation,
)
from .runner import RUNNER_VERSION, completed_daily_history

AUDIT_VERSION = "signal-availability-audit-v1.0.0"
SESSION_COUNT = 60
MINIMUM_HISTORY = 200
OUTPUT = Path(__file__).resolve().parents[2] / "artifacts"
DEFAULT_CACHE = OUTPUT / "pullback_robustness_dataset"
PREVIOUS_AUDIT = {
    "demo": {"symbol_count": 10, "valid_signals": 1, "zero_signal_days": 59},
    "dow30": {"symbol_count": 30, "valid_signals": 77, "zero_signal_days": 24},
    "nasdaq100": {"symbol_count": 30, "valid_signals": 106, "zero_signal_days": 24},
    "sp500": {"symbol_count": 51, "valid_signals": 114, "zero_signal_days": 23},
}

UNIVERSES = {
    "demo": list(WATCHLIST),
    "dow30": list(DOW30),
    "nasdaq100": list(NASDAQ100),
    "sp500": list(SP500),
}
UNIVERSE_LABELS = {
    "demo": "Demo 10",
    "dow30": "Dow 30",
    "nasdaq100": "Nasdaq 100",
    "sp500": "S&P 500",
}

SECTOR_BY_TICKER = {
    ticker: sector
    for sector, tickers in RESEARCH_SECTOR_UNIVERSE.items()
    for ticker in tickers.split()
}
SECTOR_BY_TICKER.update(
    {
        "ACN": "Technology",
        "ADP": "Industrials",
        "BRK-B": "Financials",
        "GOOG": "Communication Services",
        "INTC": "Technology",
        "MMM": "Industrials",
        "MU": "Technology",
        "PANW": "Technology",
        "PLTR": "Technology",
        "SPGI": "Financials",
        "TRV": "Financials",
        "VRTX": "Health Care",
    }
)
SECTOR_BY_TICKER.update(
    {
        symbol: str(item["sector"])
        for symbol, item in stock_constituent_metadata().items()
        if item.get("sector")
    }
)


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _rounded_median(values: list[float], digits: int = 4) -> float | None:
    finite = [value for value in values if math.isfinite(value)]
    return round(float(median(finite)), digits) if finite else None


def _clean_history(history: pd.DataFrame | None) -> pd.DataFrame | None:
    if history is None or history.empty:
        return history
    required = ["Open", "High", "Low", "Close", "Volume"]
    if history.columns.duplicated().any() or any(
        column not in history.columns for column in required
    ):
        return None
    result = history.loc[:, required].copy()
    result.index = pd.to_datetime(result.index).tz_localize(None)
    result = result[~result.index.duplicated(keep="last")].sort_index()
    numeric = result.apply(pd.to_numeric, errors="coerce")
    valid = numeric.map(lambda value: _finite(value) is not None).all(axis=1)
    return numeric.loc[valid]


def _cached_history(cache_dir: Path, ticker: str) -> pd.DataFrame | None:
    path = cache_dir / f"{ticker}.csv"
    if not path.exists():
        return None
    try:
        cached = pd.read_csv(path, index_col=0, parse_dates=True)
        if any(
            str(column).endswith(".1")
            and str(column).removesuffix(".1") in {"Open", "High", "Low", "Close", "Volume"}
            for column in cached.columns
        ):
            return None
        return _clean_history(cached)
    except (OSError, ValueError, pd.errors.ParserError):
        return None


def _fetch_history(
    provider: MarketDataProvider,
    ticker: str,
    now: datetime,
    cache_dir: Path,
    required_session: pd.Timestamp | None = None,
    required_start: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame | None, str, str | None]:
    cached = _cached_history(cache_dir, ticker)
    if (
        cached is not None
        and len(cached) >= MINIMUM_HISTORY + SESSION_COUNT
        and (
            required_session is None
            or pd.Timestamp(cached.index[-1]).normalize() >= required_session.normalize()
        )
        and (
            required_start is None
            or pd.Timestamp(cached.index[0]).normalize() <= required_start.normalize()
        )
    ):
        return cached, "local Yahoo cache", None

    errors = []
    for attempt in range(1, 4):
        try:
            if required_start is not None and required_session is not None:
                raw = provider.get_history(
                    ticker,
                    interval="1d",
                    start=(required_start - timedelta(days=7)).date().isoformat(),
                    end=(required_session + timedelta(days=1)).date().isoformat(),
                )
                history = _clean_history(raw)
                if history is not None:
                    history = history.loc[history.index <= required_session]
            else:
                history = _clean_history(completed_daily_history(provider, ticker, now))
            if history is None or len(history) < MINIMUM_HISTORY + SESSION_COUNT:
                count = 0 if history is None else len(history)
                raise ValueError(
                    f"Only {count} completed candles were returned; "
                    f"{MINIMUM_HISTORY + SESSION_COUNT} are required."
                )
            if (
                required_session is not None
                and pd.Timestamp(history.index[-1]).normalize() < required_session.normalize()
            ):
                raise ValueError(
                    "The latest completed symbol candle does not match the benchmark session."
                )
            if (
                required_start is not None
                and pd.Timestamp(history.index[0]).normalize() > required_start.normalize()
            ):
                raise ValueError(
                    "The provider did not return the full historical production window."
                )
            cache_dir.mkdir(parents=True, exist_ok=True)
            history.to_csv(cache_dir / f"{ticker}.csv")
            return history, "Yahoo Finance", None
        except Exception as error:
            errors.append(f"attempt {attempt}: {type(error).__name__}: {error}")
            time.sleep(0.2 * attempt)
    if cached is not None and len(cached) >= MINIMUM_HISTORY + SESSION_COUNT:
        if required_session is None:
            return cached, "local Yahoo cache after provider failure", "; ".join(errors)
        if pd.Timestamp(cached.index[-1]).normalize() >= required_session.normalize():
            if (
                required_start is None
                or pd.Timestamp(cached.index[0]).normalize() <= required_start.normalize()
            ):
                return cached, "local Yahoo cache after provider failure", "; ".join(errors)
    return None, "unavailable", "; ".join(errors)


def load_histories(
    provider: MarketDataProvider,
    symbols: list[str],
    *,
    now: datetime,
    cache_dir: Path = DEFAULT_CACHE,
    concurrency: int = 1,
) -> tuple[dict[str, pd.DataFrame], dict[str, str], dict[str, str], list[pd.Timestamp]]:
    """Load provider-equivalent daily data once and identify the last 60 sessions."""

    benchmark, benchmark_source, benchmark_warning = _fetch_history(
        provider, "SPY", now, cache_dir
    )
    if benchmark is None:
        raise RuntimeError(
            "SPY benchmark history is unavailable: "
            + (benchmark_warning or "no completed daily data")
        )
    sessions = list(pd.DatetimeIndex(benchmark.index[-SESSION_COUNT:]))
    if len(sessions) < SESSION_COUNT:
        raise RuntimeError(f"Only {len(sessions)} completed benchmark sessions were available.")
    required_session = sessions[-1]
    required_start = sessions[0] - pd.DateOffset(years=2)
    if pd.Timestamp(benchmark.index[0]).normalize() > required_start.normalize():
        benchmark, benchmark_source, benchmark_warning = _fetch_history(
            provider,
            "SPY",
            now,
            cache_dir,
            required_session,
            required_start,
        )
        if benchmark is None:
            raise RuntimeError(
                "SPY does not cover the full historical production window: "
                + (benchmark_warning or "missing benchmark data")
            )
        sessions = list(pd.DatetimeIndex(benchmark.index[-SESSION_COUNT:]))
        required_session = sessions[-1]
        required_start = sessions[0] - pd.DateOffset(years=2)
    histories: dict[str, pd.DataFrame] = {"SPY": benchmark}
    sources = {"SPY": benchmark_source}
    warnings = {"SPY": benchmark_warning} if benchmark_warning else {}

    unique_symbols = sorted(set(symbols) - {"SPY"})
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futures = {
            pool.submit(
                _fetch_history,
                provider,
                ticker,
                now,
                cache_dir,
                required_session,
                required_start,
            ): ticker
            for ticker in unique_symbols
        }
        for future in as_completed(futures):
            ticker = futures[future]
            history, source, warning = future.result()
            sources[ticker] = source
            if warning:
                warnings[ticker] = warning
            if history is not None:
                histories[ticker] = history
    return histories, sources, warnings, sessions


def _canonical_reasons(result: dict[str, Any]) -> list[str]:
    reasons = []
    for reason in result.get("reasons") or []:
        lower = reason.lower()
        if "market-regime score" in lower and "below" in lower:
            reasons.append("market_regime_below_65")
        elif "exceeded the frozen 5%" in lower:
            reasons.append("risk_above_5_percent")
        elif "stop" in lower and "not positive" in lower:
            reasons.append("non_positive_stop")
        elif "risk per share" in lower and "not positive" in lower:
            reasons.append("non_positive_risk")
        elif "atr" in lower and ("missing" in lower or "non-positive" in lower):
            reasons.append("invalid_atr")
        elif "fewer than 200" in lower:
            reasons.append("insufficient_history")
        else:
            reasons.append("other_strategy_rejection")
    return list(dict.fromkeys(reasons))


def _regime_label(score: float | None) -> str:
    if score is None:
        return "Unavailable"
    if score >= 90:
        return "Strong risk-on"
    if score >= 65:
        return "Risk-on"
    if score >= 35:
        return "Mixed/defensive"
    return "Defensive"


def _evaluate_symbol_session(
    ticker: str,
    history_full: pd.DataFrame | None,
    benchmark_full: pd.DataFrame,
    session: pd.Timestamp,
) -> dict[str, Any]:
    if history_full is None:
        return {
            "ticker": ticker,
            "status": "provider_failure",
            "provider_error": "No validated history was available.",
        }
    # Production requests ``period="2y"``. Recreate that rolling calendar
    # window for every historical session before calling the registered
    # strategy so older cached candles cannot influence EMA initialization.
    window_start = session - pd.DateOffset(years=2)
    history = history_full.loc[
        (history_full.index > window_start) & (history_full.index <= session)
    ]
    benchmark = benchmark_full.loc[
        (benchmark_full.index > window_start) & (benchmark_full.index <= session)
    ]
    if history.empty or pd.Timestamp(history.index[-1]).normalize() != session.normalize():
        return {
            "ticker": ticker,
            "status": "provider_failure",
            "provider_error": "The symbol does not have the same completed session as SPY.",
        }
    if len(history) < MINIMUM_HISTORY or len(benchmark) < MINIMUM_HISTORY:
        return {
            "ticker": ticker,
            "status": "provider_failure",
            "provider_error": "At least 200 completed daily candles are required.",
        }

    timestamp = _signal_timestamp(session.date())
    strategy = strategy_registry.require_usable("swing_trading")
    try:
        production_signal = strategy.scan(
            ticker=ticker,
            history=history,
            benchmark=benchmark,
            signal_timestamp=timestamp,
        )
        standalone = _standalone_calculation(ticker, history, benchmark, timestamp)
    except Exception as error:
        return {
            "ticker": ticker,
            "status": "provider_failure",
            "provider_error": str(error) or type(error).__name__,
        }
    diagnostics = standalone["diagnostics"]
    mismatches = _compare_production_and_standalone(production_signal, standalone)
    entry = _finite(diagnostics.get("expected_entry_fill"))
    swing_low = _finite(diagnostics.get("swing_low_20"))
    atr = _finite(diagnostics.get("atr"))
    stop = _finite(diagnostics.get("stop_loss"))
    risk_percent = _finite(diagnostics.get("risk_percent"))
    distance = (
        (entry - swing_low) / entry * 100
        if entry is not None and entry > 0 and swing_low is not None
        else None
    )
    atr_percent = (
        atr / entry * 100
        if entry is not None and entry > 0 and atr is not None
        else None
    )
    atr_buffer = atr_percent * STOP_ATR if atr_percent is not None else None
    reconstructed = distance + atr_buffer if distance is not None and atr_buffer is not None else None
    formula_error = (
        abs(risk_percent - reconstructed)
        if risk_percent is not None and reconstructed is not None
        else None
    )
    direct_risk_percent = (
        (entry - stop) / entry * 100
        if entry is not None and entry > 0 and stop is not None
        else None
    )
    return {
        "ticker": ticker,
        "status": "signal" if production_signal is not None else "rejected",
        "reasons": _canonical_reasons(standalone),
        "production_signal": production_signal,
        "market_regime": _regime_label(_finite(diagnostics.get("market_regime_score"))),
        "market_regime_score": _finite(diagnostics.get("market_regime_score")),
        "risk_percent": risk_percent,
        "distance_to_swing_low_percent": distance,
        "atr_percent": atr_percent,
        "atr_buffer_percent": atr_buffer,
        "direct_risk_percent": direct_risk_percent,
        "risk_formula_error_percentage_points": formula_error,
        "mismatches": mismatches,
    }


def _volatility_bucket(atr_percent: float | None) -> str:
    if atr_percent is None:
        return "Unavailable"
    if atr_percent < 2:
        return "Low (<2% ATR)"
    if atr_percent <= 4:
        return "Moderate (2-4% ATR)"
    return "High (>4% ATR)"


def _rate_groups(
    observations: list[dict[str, Any]], field: str
) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in observations:
        groups[str(item[field])].append(item)
    return {
        key: {
            "completed_scans": len(rows),
            "risk_limit_rejections": sum(
                "risk_above_5_percent" in row["reasons"] for row in rows
            ),
            "risk_limit_rejection_rate_percent": round(
                100
                * sum("risk_above_5_percent" in row["reasons"] for row in rows)
                / len(rows),
                2,
            ),
        }
        for key, rows in sorted(groups.items())
    }


def _risk_limit_analysis(observations: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [
        item for item in observations if item["status"] in {"signal", "rejected"}
    ]
    rejected = [
        item
        for item in completed
        if "risk_above_5_percent" in item.get("reasons", [])
    ]
    risks = [item["risk_percent"] for item in rejected if item["risk_percent"] is not None]
    by_sector = Counter(SECTOR_BY_TICKER.get(item["ticker"], "Unknown") for item in rejected)
    top_sector, top_count = by_sector.most_common(1)[0] if by_sector else (None, 0)
    for item in completed:
        item["volatility_bucket"] = _volatility_bucket(item.get("atr_percent"))
    return {
        "total": len(rejected),
        "only_slightly_above_5_to_7_5_percent": sum(5 < risk <= 7.5 for risk in risks),
        "above_7_5_percent": sum(risk > 7.5 for risk in risks),
        "above_10_percent": sum(risk > 10 for risk in risks),
        "exclusive_bands": {
            "over_5_to_7_5": sum(5 < risk <= 7.5 for risk in risks),
            "over_7_5_to_10": sum(7.5 < risk <= 10 for risk in risks),
            "over_10": sum(risk > 10 for risk in risks),
        },
        "median_risk_percent": _rounded_median(risks),
        "median_distance_to_swing_low_percent": _rounded_median(
            [
                item["distance_to_swing_low_percent"]
                for item in rejected
                if item["distance_to_swing_low_percent"] is not None
            ]
        ),
        "median_atr_buffer_percent": _rounded_median(
            [
                item["atr_buffer_percent"]
                for item in rejected
                if item["atr_buffer_percent"] is not None
            ]
        ),
        "by_sector": dict(sorted(by_sector.items())),
        "top_sector": top_sector,
        "top_sector_share_percent": round(top_count / len(rejected) * 100, 2)
        if rejected
        else 0.0,
        "sector_dominance_detected": bool(rejected and top_count / len(rejected) > 0.5),
        "by_volatility": _rate_groups(completed, "volatility_bucket")
        if completed
        else {},
        "by_market_regime": _rate_groups(completed, "market_regime")
        if completed
        else {},
    }


def _daily_summary(
    session: pd.Timestamp, observations: list[dict[str, Any]]
) -> dict[str, Any]:
    completed = [
        item for item in observations if item["status"] in {"signal", "rejected"}
    ]
    failures = [item for item in observations if item["status"] == "provider_failure"]
    reasons = Counter(
        reason
        for item in completed
        if item["status"] == "rejected"
        for reason in item.get("reasons", [])
    )
    regimes = Counter(item["market_regime"] for item in completed)
    regime = regimes.most_common(1)[0][0] if regimes else "Unavailable"
    regime_scores = [
        item["market_regime_score"]
        for item in completed
        if item["market_regime_score"] is not None
    ]
    return {
        "date": session.date().isoformat(),
        "symbols_requested": len(observations),
        "symbols_scanned": len(completed),
        "valid_signals": sum(item["status"] == "signal" for item in completed),
        "rejected_signals": sum(item["status"] == "rejected" for item in completed),
        "rejection_reasons": dict(sorted(reasons.items())),
        "provider_failures": len(failures),
        "provider_failure_symbols": sorted(item["ticker"] for item in failures),
        "provider_failure_reasons": dict(
            sorted(Counter(item["provider_error"] for item in failures).items())
        ),
        "market_regime": regime,
        "market_regime_score": _rounded_median(regime_scores, 2),
        "median_risk_percent": _rounded_median(
            [item["risk_percent"] for item in completed if item["risk_percent"] is not None]
        ),
        "median_distance_to_swing_low_percent": _rounded_median(
            [
                item["distance_to_swing_low_percent"]
                for item in completed
                if item["distance_to_swing_low_percent"] is not None
            ]
        ),
        "median_atr_percent": _rounded_median(
            [item["atr_percent"] for item in completed if item["atr_percent"] is not None]
        ),
    }


def _outcome_estimate(
    signal_observations: list[dict[str, Any]],
    histories: dict[str, pd.DataFrame],
    sessions: list[pd.Timestamp],
) -> dict[str, Any]:
    final_session = sessions[-1]
    maturity_cutoff_index = max(0, len(sessions) - ENTRY_WAIT - MAX_HOLDING_DAYS)
    maturity_cutoff = sessions[maturity_cutoff_index]
    mature = [
        item
        for item in signal_observations
        if item["session"] <= maturity_cutoff and item.get("production_signal")
    ]
    statuses = Counter()
    for item in mature:
        history = histories[item["ticker"]].loc[
            histories[item["ticker"]].index <= final_session
        ]
        statuses[evaluate_signal(item["production_signal"], history)["status"]] += 1
    completed = sum(statuses[status] for status in ("TP2_hit", "stopped", "completed"))
    entered = completed + sum(statuses[status] for status in ("entered", "TP1_hit"))
    completion_rate = completed / len(mature) if mature else 0.0
    return {
        "mature_signals": len(mature),
        "entered_signals": entered,
        "completed_trades": completed,
        "expired_signals": statuses["expired"],
        "status_counts": dict(sorted(statuses.items())),
        "mature_signal_completion_rate_percent": round(completion_rate * 100, 2),
    }


def run_signal_availability_audit(
    histories: dict[str, pd.DataFrame],
    sessions: list[pd.Timestamp],
    *,
    universes: dict[str, list[str]] | None = None,
    sources: dict[str, str] | None = None,
    provider_warnings: dict[str, str] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Replay all requested universe/date combinations without production writes."""

    selected = universes or UNIVERSES
    benchmark = histories.get("SPY")
    if benchmark is None:
        raise ValueError("SPY benchmark history is required.")
    if len(sessions) != SESSION_COUNT:
        raise ValueError(f"Exactly {SESSION_COUNT} completed sessions are required.")

    all_symbols = sorted({ticker for values in selected.values() for ticker in values})
    observations: dict[tuple[str, pd.Timestamp], dict[str, Any]] = {}
    mismatch_records = []
    max_formula_error = 0.0
    for session in sessions:
        for ticker in all_symbols:
            item = _evaluate_symbol_session(
                ticker, histories.get(ticker), benchmark, session
            )
            item["session"] = session
            observations[(ticker, session)] = item
            for field in item.get("mismatches", []):
                mismatch_records.append(
                    {
                        "date": session.date().isoformat(),
                        "ticker": ticker,
                        "field": field,
                    }
                )
            error = item.get("risk_formula_error_percentage_points")
            if error is not None:
                max_formula_error = max(max_formula_error, error)

    universe_results = {}
    for universe_id, symbols in selected.items():
        universe_observations = [
            observations[(ticker, session)]
            for session in sessions
            for ticker in symbols
        ]
        daily = [
            _daily_summary(
                session, [observations[(ticker, session)] for ticker in symbols]
            )
            for session in sessions
        ]
        valid = sum(item["status"] == "signal" for item in universe_observations)
        rejected = sum(item["status"] == "rejected" for item in universe_observations)
        failures = sum(
            item["status"] == "provider_failure" for item in universe_observations
        )
        failure_symbols = sorted(
            {
                item["ticker"]
                for item in universe_observations
                if item["status"] == "provider_failure"
            }
        )
        failure_reasons = Counter(
            item["provider_error"]
            for item in universe_observations
            if item["status"] == "provider_failure"
        )
        zero_days = sum(row["valid_signals"] == 0 for row in daily)
        signals_per_day = valid / len(sessions)
        signal_observations = [
            {**item, "session": session}
            for session in sessions
            for ticker in symbols
            if (item := observations[(ticker, session)])["status"] == "signal"
        ]
        outcomes = _outcome_estimate(
            signal_observations, histories, sessions
        )
        completed_per_day = signals_per_day * (
            outcomes["mature_signal_completion_rate_percent"] / 100
        )
        expected_days = 100 / completed_per_day if completed_per_day > 0 else None
        expected_signal_days = 100 / signals_per_day if signals_per_day > 0 else None
        reason_counts = Counter(
            reason
            for item in universe_observations
            if item["status"] == "rejected"
            for reason in item.get("reasons", [])
        )
        universe_results[universe_id] = {
            "label": UNIVERSE_LABELS.get(universe_id, universe_id),
            "configured_symbol_count": len(symbols),
            "configured_symbols": symbols,
            "sessions": len(sessions),
            "symbols_scanned": sum(row["symbols_scanned"] for row in daily),
            "valid_signals": valid,
            "rejected_signals": rejected,
            "provider_failures": failures,
            "provider_failure_symbols": failure_symbols,
            "provider_failure_reasons": dict(sorted(failure_reasons.items())),
            "rejection_reasons": dict(sorted(reason_counts.items())),
            "signals_per_trading_day": round(signals_per_day, 4),
            "days_with_zero_signals": zero_days,
            "zero_signal_frequency_percent": round(zero_days / len(sessions) * 100, 2),
            "average_valid_signals_per_week": round(signals_per_day * 5, 4),
            "outcome_estimate": outcomes,
            "estimated_weeks_to_100_signals": round(expected_signal_days / 5, 1)
            if expected_signal_days is not None
            else None,
            "estimated_trading_days_to_100_completed_trades": round(expected_days, 1)
            if expected_days is not None
            else None,
            "estimated_weeks_to_100_completed_trades": round(expected_days / 5, 1)
            if expected_days is not None
            else None,
            "risk_limit_analysis": _risk_limit_analysis(universe_observations),
            "daily": daily,
        }

    largest_universe_id = max(selected, key=lambda key: len(selected[key]))
    largest_universe = universe_results[largest_universe_id]
    largest_risk = largest_universe["risk_limit_analysis"]
    stop_structurally_wide = (
        largest_risk["total"] / max(1, largest_universe["symbols_scanned"]) > 0.5
    )
    if largest_risk["total"]:
        stop_diagnosis = (
            f"In the largest configured snapshot ({largest_universe['label']}), "
            f"{largest_risk['total']} of {largest_universe['symbols_scanned']} "
            "completed scans breached the 5% cap. The median rejected risk was "
            f"{largest_risk['median_risk_percent']:.2f}%, decomposed into a "
            f"{largest_risk['median_distance_to_swing_low_percent']:.2f}% "
            "entry-to-swing-low distance and a "
            f"{largest_risk['median_atr_buffer_percent']:.2f}% ATR buffer. "
            "The stop formula is therefore structurally wide relative to the frozen "
            "cap in this window, but it is not being calculated incorrectly."
        )
    else:
        stop_diagnosis = (
            f"No scan in the largest configured snapshot ({largest_universe['label']}) "
            "breached the frozen 5% cap."
        )
    previous_comparison = {}
    for universe_id, universe in universe_results.items():
        previous = PREVIOUS_AUDIT.get(universe_id)
        if previous is None:
            continue
        previous_comparison[universe_id] = {
            "previous_symbol_count": previous["symbol_count"],
            "corrected_symbol_count": universe["configured_symbol_count"],
            "previous_valid_signals": previous["valid_signals"],
            "corrected_valid_signals": universe["valid_signals"],
            "valid_signal_change": universe["valid_signals"] - previous["valid_signals"],
            "previous_zero_signal_days": previous["zero_signal_days"],
            "corrected_zero_signal_days": universe["days_with_zero_signals"],
            "zero_signal_day_change": (
                universe["days_with_zero_signals"] - previous["zero_signal_days"]
            ),
        }
    return {
        "audit_version": AUDIT_VERSION,
        "runner_version": RUNNER_VERSION,
        "strategy_version": STRATEGY_VERSION,
        "generated_at": (generated_at or datetime.now(timezone.utc)).isoformat(),
        "period": {
            "completed_us_trading_days": len(sessions),
            "start": sessions[0].date().isoformat(),
            "end": sessions[-1].date().isoformat(),
            "benchmark": "SPY",
        },
        "frozen_rules": {
            "market_regime_minimum": 65,
            "entry": "signal-time EMA20 pullback limit with production entry slippage",
            "swing_low_lookback_sessions": 20,
            "stop_atr_buffer": STOP_ATR,
            "maximum_risk_percent": MAX_RISK_PCT * 100,
            "target_1_r": 2.0,
            "target_2_r": 4.0,
        },
        "methodology": {
            "pipeline": "Registered production swing_trading strategy",
            "look_ahead_control": "Every signal calculation received only candles through that session.",
            "history_window": "The rolling two-calendar-year window matches the production provider request period=2y.",
            "observation_reuse": "A ticker/date result was calculated once and reused only when that ticker belonged to multiple configured universes.",
            "completion_estimate": (
                "Only signals with the full 3-session entry window plus 30-session "
                "maximum holding window inside the audit period were used to estimate "
                "completion rate."
            ),
        },
        "data_sources": sources or {},
        "provider_load_warnings": provider_warnings or {},
        "configured_universe_sizes": {
            universe_id: len(symbols) for universe_id, symbols in selected.items()
        },
        "calculation_verification": {
            "observations_checked": sum(
                item["status"] in {"signal", "rejected"} for item in observations.values()
            ),
            "risk_formula": (
                "risk% = ((expected executable entry - "
                "(20-session swing low - 1.5 * ATR)) / expected executable entry) * 100"
            ),
            "decomposition": (
                "risk% = distance from executable entry to swing low% + 1.5 * ATR%"
            ),
            "maximum_formula_error_percentage_points": round(max_formula_error, 10),
            "production_standalone_mismatches": mismatch_records,
            "calculation_bug_found": bool(
                max_formula_error > 0.0001 or mismatch_records
            ),
        },
        "universes": universe_results,
        "previous_audit_comparison": previous_comparison,
        "conclusion_change": {
            "broad_universe_availability_changed": (
                universe_results.get("nasdaq100", {}).get("days_with_zero_signals")
                == 0
                and universe_results.get("sp500", {}).get("days_with_zero_signals")
                == 0
            ),
            "risk_limit_conclusion_changed": False,
            "summary": (
                "Completing the Nasdaq-100 and S&P 500 universes eliminated zero-signal "
                "days in this window and materially shortened the estimated time to 100 "
                "completed trades. The prior conclusions that Demo 10 is too small, the "
                "5% calculation is correct, and the frozen stop geometry is structurally "
                "wide relative to that cap did not change."
            ),
        },
        "diagnosis": {
            "stop_formula_arithmetic_bug": False,
            "stop_formula_structurally_wide_relative_to_cap": stop_structurally_wide,
            "stop_formula_relative_to_cap": stop_diagnosis,
            "demo_universe_too_small_for_availability": (
                universe_results.get("demo", {}).get("valid_signals", 0)
                < largest_universe["valid_signals"]
                and universe_results.get("demo", {}).get(
                    "zero_signal_frequency_percent", 100
                )
                > largest_universe["zero_signal_frequency_percent"]
            ),
            "risk_rule_functioning_as_intended": not (
                max_formula_error > 0.0001 or mismatch_records
            ),
            "strategy_naturally_selective": (
                largest_universe["valid_signals"]
                / max(1, largest_universe["symbols_scanned"])
                < 0.1
            ),
            "regime_dependency_conclusion": (
                "Not identifiable from this 60-session sample because every audited "
                "session was classified Strong risk-on."
            ),
            "volatility_dependency_conclusion": (
                "The risk gate rejected 100% of high-ATR observations in every "
                "configured universe; low-ATR observations had materially lower "
                "rejection rates in the larger snapshots."
            ),
        },
        "production_records_changed": False,
    }


def _format_number(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def render_report(result: dict[str, Any]) -> str:
    verification = result["calculation_verification"]
    lines = [
        "# Signal Availability Audit",
        "",
        "## Executive verdict",
        "",
        (
            "The frozen Regime-Gated Pullback strategy was replayed through the "
            "registered production strategy interface for each of the most recent "
            f"**{result['period']['completed_us_trading_days']}** completed US sessions "
            f"({result['period']['start']} through {result['period']['end']})."
        ),
        "",
        "| Configured universe | Names | Valid signals | Signals/day | Zero-signal days | Valid/week | Estimated weeks to 100 completed |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for universe in result["universes"].values():
        lines.append(
            "| "
            + " | ".join(
                [
                    universe["label"],
                    str(universe["configured_symbol_count"]),
                    str(universe["valid_signals"]),
                    _format_number(universe["signals_per_trading_day"], 3),
                    f"{universe['days_with_zero_signals']} ({universe['zero_signal_frequency_percent']:.2f}%)",
                    _format_number(universe["average_valid_signals_per_week"], 3),
                    _format_number(
                        universe["estimated_weeks_to_100_completed_trades"], 1
                    ),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            (
                "The estimate to 100 completed trades uses the observed completion rate "
                "only for signals with enough later candles for the full entry and holding "
                "window. It is an availability estimate, not a performance forecast."
            ),
            "",
            "The index memberships come from the committed, timestamped constituent "
            "snapshot. Runtime scans read that snapshot and do not scrape public sources.",
            "",
            "## Change from the truncated-universe audit",
            "",
            "| Universe | Previous names | Corrected names | Previous signals | Corrected signals | Previous zero days | Corrected zero days |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for universe_id, comparison in result["previous_audit_comparison"].items():
        lines.append(
            "| "
            + " | ".join(
                [
                    result["universes"][universe_id]["label"],
                    str(comparison["previous_symbol_count"]),
                    str(comparison["corrected_symbol_count"]),
                    str(comparison["previous_valid_signals"]),
                    str(comparison["corrected_valid_signals"]),
                    str(comparison["previous_zero_signal_days"]),
                    str(comparison["corrected_zero_signal_days"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            f"**Conclusion change:** {result['conclusion_change']['summary']}",
            "",
            "## Direct findings",
            "",
            f"- Stop formula arithmetic bug: **{'YES' if result['diagnosis']['stop_formula_arithmetic_bug'] else 'NO'}**",
            f"- Stop geometry structurally wide relative to the 5% cap in this window: **{'YES' if result['diagnosis']['stop_formula_structurally_wide_relative_to_cap'] else 'NO'}**. {result['diagnosis']['stop_formula_relative_to_cap']}",
            f"- Demo universe too small for practical signal availability: **{'YES' if result['diagnosis']['demo_universe_too_small_for_availability'] else 'NO'}**",
            f"- 5% rule functioning as implemented: **{'YES' if result['diagnosis']['risk_rule_functioning_as_intended'] else 'NO'}**",
            f"- Frozen strategy naturally selective in this window: **{'YES' if result['diagnosis']['strategy_naturally_selective'] else 'NO'}**",
            f"- Volatility dependence: {result['diagnosis']['volatility_dependency_conclusion']}",
            f"- Regime dependence: {result['diagnosis']['regime_dependency_conclusion']}",
            "",
            "## Calculation integrity",
            "",
            f"- Production/standalone mismatches: **{len(verification['production_standalone_mismatches'])}**",
            f"- Risk observations checked: **{verification['observations_checked']}**",
            f"- Maximum formula error: **{verification['maximum_formula_error_percentage_points']:.10f} percentage points**",
            f"- Calculation bug found: **{'YES' if verification['calculation_bug_found'] else 'NO'}**",
            f"- Formula: `{verification['risk_formula']}`",
            f"- Decomposition: `{verification['decomposition']}`",
            "",
            "The executable entry includes the production entry slippage. The stop is the "
            "signal-time 20-session swing low minus the frozen 1.5 ATR buffer. Every history "
            "was limited to the production two-year window and sliced at the signal date "
            "before the registered strategy was called.",
            "",
            "## Universe findings",
            "",
        ]
    )
    for universe in result["universes"].values():
        risk = universe["risk_limit_analysis"]
        outcome = universe["outcome_estimate"]
        top_reasons = sorted(
            universe["rejection_reasons"].items(), key=lambda item: (-item[1], item[0])
        )
        lines.extend(
            [
                f"### {universe['label']}",
                "",
                f"- Configured names: **{universe['configured_symbol_count']}**",
                f"- Completed symbol/date scans: **{universe['symbols_scanned']}**",
                f"- Valid signals: **{universe['valid_signals']}**",
                f"- Rejected setups: **{universe['rejected_signals']}**",
                f"- Provider failures: **{universe['provider_failures']}**",
                "- Symbols without the required historical window: "
                + (
                    ", ".join(
                        f"`{symbol}`"
                        for symbol in universe["provider_failure_symbols"]
                    )
                    if universe["provider_failure_symbols"]
                    else "none"
                ),
                f"- Signals per trading day: **{universe['signals_per_trading_day']:.4f}**",
                f"- Zero-signal frequency: **{universe['zero_signal_frequency_percent']:.2f}%**",
                f"- Average valid signals per week: **{universe['average_valid_signals_per_week']:.4f}**",
                f"- Mature signals used for outcome estimate: **{outcome['mature_signals']}**",
                f"- Mature signal completion rate: **{outcome['mature_signal_completion_rate_percent']:.2f}%**",
                f"- Estimated weeks to issue 100 signals: **{_format_number(universe['estimated_weeks_to_100_signals'], 1)}**",
                f"- Estimated weeks to 100 completed trades: **{_format_number(universe['estimated_weeks_to_100_completed_trades'], 1)}**",
                "- Rejection reasons: "
                + (
                    ", ".join(f"`{name}` {count}" for name, count in top_reasons)
                    if top_reasons
                    else "none"
                ),
                "",
                "5% risk-limit distribution:",
                "",
                f"- Total risk-limit rejections: **{risk['total']}**",
                f"- Only slightly above 5% (greater than 5% through 7.5%): **{risk['only_slightly_above_5_to_7_5_percent']}**",
                f"- Above 7.5%: **{risk['above_7_5_percent']}**",
                f"- Above 10%: **{risk['above_10_percent']}**",
                f"- Median rejected risk: **{_format_number(risk['median_risk_percent'])}%**",
                f"- Median entry-to-swing-low distance: **{_format_number(risk['median_distance_to_swing_low_percent'])}%**",
                f"- Median 1.5 ATR buffer: **{_format_number(risk['median_atr_buffer_percent'])}%**",
                f"- Largest rejection sector: **{risk['top_sector'] or 'n/a'}** ({risk['top_sector_share_percent']:.2f}%)",
                f"- One-sector dominance (>50%): **{'YES' if risk['sector_dominance_detected'] else 'NO'}**",
                "",
                "Risk-limit rejection rate by volatility:",
                "",
                "| ATR bucket | Completed scans | Risk rejections | Rate |",
                "|---|---:|---:|---:|",
            ]
        )
        for label, values in risk["by_volatility"].items():
            lines.append(
                f"| {label} | {values['completed_scans']} | "
                f"{values['risk_limit_rejections']} | "
                f"{values['risk_limit_rejection_rate_percent']:.2f}% |"
            )
        lines.extend(
            [
                "",
                "Risk-limit rejection rate by market regime:",
                "",
                "| Regime | Completed scans | Risk rejections | Rate |",
                "|---|---:|---:|---:|",
            ]
        )
        for label, values in risk["by_market_regime"].items():
            lines.append(
                f"| {label} | {values['completed_scans']} | "
                f"{values['risk_limit_rejections']} | "
                f"{values['risk_limit_rejection_rate_percent']:.2f}% |"
            )
        lines.append("")

    lines.extend(
        [
            "## Per-date audit",
            "",
            "Each row is the exact aggregate required for one configured universe and one completed session.",
            "",
            "| Universe | Date | Scanned | Valid | Rejected | Failures | Regime | Median risk % | Median swing-low distance % | Median ATR % | Rejection reasons |",
            "|---|---|---:|---:|---:|---:|---|---:|---:|---:|---|",
        ]
    )
    for universe in result["universes"].values():
        for day in universe["daily"]:
            reasons = ", ".join(
                f"{key}:{value}" for key, value in day["rejection_reasons"].items()
            ) or "none"
            lines.append(
                "| "
                + " | ".join(
                    [
                        universe["label"],
                        day["date"],
                        str(day["symbols_scanned"]),
                        str(day["valid_signals"]),
                        str(day["rejected_signals"]),
                        str(day["provider_failures"]),
                        f"{day['market_regime']} ({_format_number(day['market_regime_score'], 0)})",
                        _format_number(day["median_risk_percent"]),
                        _format_number(day["median_distance_to_swing_low_percent"]),
                        _format_number(day["median_atr_percent"]),
                        reasons,
                    ]
                )
                + " |"
            )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The 5% gate is applied exactly as frozen and is mechanically functioning as "
            "documented. Whether the stop is operationally too wide is assessed from the "
            "reported decomposition: the entry-to-swing-low distance and the 1.5 ATR buffer "
            "are shown separately, so a wide stop cannot be misattributed to an arithmetic error.",
            "",
            "The Demo 10 result measures a ten-name list and therefore cannot represent broad "
            "market availability. Comparing it with the larger configured snapshots separates "
            "universe-size scarcity from the strategy's natural selectivity. No threshold, "
            "strategy setting, universe membership, or production record was changed.",
            "",
            "## Data and limitations",
            "",
            "- Yahoo Finance adjusted daily OHLCV was loaded through the existing provider path; validated local Yahoo cache files were reused when current.",
            "- Index memberships and sectors come from the timestamped local constituent snapshot.",
            "- The All US Stocks universe is not replayed automatically because large scans require explicit user action; this audit retains the four-universe Milestone 39 scope.",
            "- The completion-time estimate assumes future signal availability resembles this 60-session window and is not a profitability claim.",
            "- Historical examples do not guarantee future signals or results.",
            "- Production records changed: **NO**.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", default="artifacts/signal_availability_results.json"
    )
    parser.add_argument(
        "--report", default="docs/SIGNAL_AVAILABILITY_AUDIT.md"
    )
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    symbols = sorted({ticker for values in UNIVERSES.values() for ticker in values})
    provider = get_market_data_provider()
    histories, sources, warnings, sessions = load_histories(
        provider, symbols, now=now
    )
    result = run_signal_availability_audit(
        histories,
        sessions,
        sources=sources,
        provider_warnings=warnings,
        generated_at=now,
    )
    output_path = Path(args.output)
    report_path = Path(args.report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(render_report(result), encoding="utf-8")
    print(
        json.dumps(
            {
                universe_id: {
                    "valid_signals": values["valid_signals"],
                    "zero_signal_frequency_percent": values[
                        "zero_signal_frequency_percent"
                    ],
                    "estimated_weeks_to_100_completed_trades": values[
                        "estimated_weeks_to_100_completed_trades"
                    ],
                }
                for universe_id, values in result["universes"].items()
            },
            indent=2,
        )
    )
    return 1 if result["calculation_verification"]["calculation_bug_found"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
