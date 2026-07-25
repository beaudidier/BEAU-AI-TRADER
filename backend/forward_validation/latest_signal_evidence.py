"""Audit and publish every valid signal from the latest production-path replay."""

from __future__ import annotations

import hashlib
import html
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from strategies import strategy_registry
from strategies.swing_strategy import MAX_RISK_PCT, STRATEGY_VERSION

ROOT = Path(__file__).resolve().parents[2]
REPLAY_PATH = ROOT / "artifacts" / "production_path_replay.json"
UNIVERSE_PATH = ROOT / "backend" / "universe" / "data" / "stock_universes.json"
CACHE_ROOT = ROOT / "artifacts" / "forward_validation_cache"
ARTIFACT_PATH = ROOT / "artifacts" / "latest_signal_evidence.json"
PUBLIC_ROOT = ROOT / "frontend" / "public" / "latest-signals"
PUBLIC_CHART_ROOT = PUBLIC_ROOT / "charts"
PUBLIC_SUMMARY_PATH = PUBLIC_ROOT / "summary.json"
COMPARISON_FIELDS = (
    "ticker",
    "signal_timestamp",
    "signal_price",
    "proposed_pullback_entry",
    "expected_entry_fill",
    "stop_loss",
    "target_1",
    "target_2",
    "market_regime",
    "market_regime_score",
    "confidence",
    "strategy_version",
    "data_timestamp",
)


def _close(left: Any, right: Any, tolerance: float = 1e-6) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=tolerance, abs_tol=tolerance)
    return left == right


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_history(path: Path, replay_date: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Raw OHLCV cache is missing: {path}")
    history = pd.read_csv(path, index_col=0, parse_dates=True)
    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = sorted(required - set(history.columns))
    if missing:
        raise ValueError(f"{path.name} is missing OHLCV fields: {', '.join(missing)}")
    history.index = pd.to_datetime(history.index).tz_localize(None)
    history = history.loc[history.index <= pd.Timestamp(replay_date)].copy()
    if history.empty or history.index[-1].date().isoformat() != replay_date:
        raise ValueError(f"{path.name} does not contain replay candle {replay_date}.")
    if history.index.has_duplicates or not history.index.is_monotonic_increasing:
        raise ValueError(f"{path.name} contains invalid market-date ordering.")
    if history.loc[:, sorted(required)].isna().any().any():
        raise ValueError(f"{path.name} contains incomplete OHLCV candles.")
    return history


def _universe_metadata() -> dict[str, dict[str, str]]:
    payload = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))
    constituents = payload["universes"]["sp500"]["constituents"]
    return {
        item["symbol"]: {
            "company_name": item.get("name") or item["symbol"],
            "sector": item.get("sector") or "Unclassified",
        }
        for item in constituents
    }


def _render_chart(
    evidence: dict[str, Any],
    history: pd.DataFrame,
    ema20: pd.Series,
    ema50: pd.Series,
) -> dict[str, Any]:
    ticker = evidence["ticker"]
    levels = evidence["levels"]
    window = history.tail(70)
    ema20_window = ema20.loc[window.index]
    ema50_window = ema50.loc[window.index]
    width, height = 1200, 680
    left, right, top, bottom = 72, 1120, 92, 594
    prices = [
        *pd.to_numeric(window["Low"], errors="raise").tolist(),
        *pd.to_numeric(window["High"], errors="raise").tolist(),
        levels["pullback_entry"],
        levels["swing_low"],
        levels["stop"],
        levels["tp1"],
        levels["tp2"],
    ]
    minimum, maximum = min(prices), max(prices)
    padding = max((maximum - minimum) * 0.06, maximum * 0.005)
    minimum -= padding
    maximum += padding
    count = len(window)

    def x(position: int) -> float:
        return left + (right - left) * position / max(1, count - 1)

    def y(price: float) -> float:
        return bottom - (float(price) - minimum) / (maximum - minimum) * (bottom - top)

    chart_path = PUBLIC_CHART_ROOT / f"{ticker.lower().replace('-', '_')}.svg"
    attributes = {
        "signal-price": evidence["signal_price"],
        "ema20": levels["ema20"],
        "ema50": levels["ema50"],
        "pullback-entry": levels["pullback_entry"],
        "swing-low": levels["swing_low"],
        "stop": levels["stop"],
        "tp1": levels["tp1"],
        "tp2": levels["tp2"],
        "risk-percent": evidence["risk_percent"],
        "signal-date": evidence["signal_date"],
    }
    attribute_text = " ".join(
        f'data-{name}="{html.escape(str(value))}"'
        for name, value in attributes.items()
    )
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" '
            f'role="img" {attribute_text}>'
        ),
        f"<title>{html.escape(ticker)} latest replay signal evidence</title>",
        (
            f"<desc>Completed daily candles through {evidence['signal_date']} "
            "with frozen pullback strategy levels.</desc>"
        ),
        '<rect width="1200" height="680" fill="#020617"/>',
        (
            f'<text x="72" y="34" fill="#f8fafc" font-family="sans-serif" '
            f'font-size="22" font-weight="600">{html.escape(ticker)} · '
            f'{html.escape(evidence["company_name"])} · Replay signal</text>'
        ),
        (
            f'<text x="72" y="62" fill="#94a3b8" font-family="sans-serif" '
            f'font-size="14">Signal {html.escape(evidence["signal_date"])} · '
            f'Regime score {evidence["market_regime_score"]:.0f} · '
            f'{html.escape(evidence["market_regime"])}</text>'
        ),
    ]
    for tick in range(6):
        price = minimum + (maximum - minimum) * tick / 5
        py = y(price)
        parts.append(
            f'<line x1="{left}" y1="{py:.2f}" x2="{right}" y2="{py:.2f}" '
            'stroke="#1e293b" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{right + 10}" y="{py + 4:.2f}" fill="#64748b" '
            f'font-family="monospace" font-size="11">{price:.2f}</text>'
        )

    candle_width = max(2.0, min(8.0, (right - left) / count * 0.62))
    for position, (_, candle) in enumerate(window.iterrows()):
        px = x(position)
        opening, high, low, closing = (
            float(candle[key]) for key in ("Open", "High", "Low", "Close")
        )
        color = "#22c55e" if closing >= opening else "#ef4444"
        body_top = min(y(opening), y(closing))
        body_bottom = max(y(opening), y(closing))
        parts.append(
            f'<line x1="{px:.2f}" y1="{y(high):.2f}" x2="{px:.2f}" '
            f'y2="{y(low):.2f}" stroke="{color}" stroke-width="1"/>'
        )
        parts.append(
            f'<rect x="{px - candle_width / 2:.2f}" y="{body_top:.2f}" '
            f'width="{candle_width:.2f}" height="{max(1.2, body_bottom - body_top):.2f}" '
            f'fill="{color}"/>'
        )

    def polyline(series: pd.Series, color: str) -> None:
        points = " ".join(
            f"{x(position):.2f},{y(float(value)):.2f}"
            for position, value in enumerate(series)
        )
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>'
        )

    polyline(ema20_window, "#f59e0b")
    polyline(ema50_window, "#38bdf8")
    line_specs = (
        ("Pullback entry", levels["pullback_entry"], "#22d3ee", ""),
        ("Swing low", levels["swing_low"], "#94a3b8", "6 4"),
        ("Stop", levels["stop"], "#fb7185", ""),
        ("TP1", levels["tp1"], "#4ade80", ""),
        ("TP2", levels["tp2"], "#c084fc", ""),
    )
    for label, price, color, dash in line_specs:
        dash_attribute = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(
            f'<line x1="{left}" y1="{y(price):.2f}" x2="{right}" '
            f'y2="{y(price):.2f}" stroke="{color}" stroke-width="1.5"'
            f"{dash_attribute}/>"
        )
        parts.append(
            f'<text x="{left + 6}" y="{y(price) - 5:.2f}" fill="{color}" '
            f'font-family="sans-serif" font-size="11">{label} {price:.2f}</text>'
        )

    marker_x = x(count - 1)
    marker_y = y(evidence["signal_price"])
    parts.extend(
        [
            (
                f'<line x1="{marker_x:.2f}" y1="{top}" x2="{marker_x:.2f}" '
                f'y2="{bottom}" stroke="#f8fafc" stroke-width="1" '
                'stroke-dasharray="3 4"/>'
            ),
            f'<circle cx="{marker_x:.2f}" cy="{marker_y:.2f}" r="5" fill="#f8fafc"/>',
            (
                f'<text x="{marker_x - 8:.2f}" y="{top + 15}" text-anchor="end" '
                'fill="#f8fafc" font-family="sans-serif" font-size="11">Signal</text>'
            ),
        ]
    )
    tick_positions = sorted(
        {0, count - 1, *(round((count - 1) * index / 5) for index in range(1, 5))}
    )
    for position in tick_positions:
        parts.append(
            f'<text x="{x(position):.2f}" y="{bottom + 28}" text-anchor="middle" '
            f'fill="#64748b" font-family="monospace" font-size="11">'
            f"{window.index[position].date()}</text>"
        )
    parts.extend(
        [
            '<line x1="72" y1="632" x2="96" y2="632" stroke="#f59e0b" stroke-width="2"/>',
            '<text x="102" y="636" fill="#94a3b8" font-family="sans-serif" font-size="11">EMA20</text>',
            '<line x1="176" y1="632" x2="200" y2="632" stroke="#38bdf8" stroke-width="2"/>',
            '<text x="206" y="636" fill="#94a3b8" font-family="sans-serif" font-size="11">EMA50</text>',
            (
                '<text x="1120" y="654" text-anchor="end" fill="#475569" '
                'font-family="sans-serif" font-size="11">Replay evidence · '
                "Frozen strategy · Paper trading only</text>"
            ),
            "</svg>",
        ]
    )
    chart_path.write_text("\n".join(parts), encoding="utf-8")
    return {
        "public_url": f"/latest-signals/charts/{chart_path.name}",
        "file": str(chart_path.relative_to(ROOT)),
        "window_start": window.index[0].date().isoformat(),
        "window_end": window.index[-1].date().isoformat(),
        "values": attributes,
    }


def generate_latest_signal_evidence() -> dict[str, Any]:
    replay = json.loads(REPLAY_PATH.read_text(encoding="utf-8"))
    replay_date = str(replay["replay_date"])
    replay_signals = [
        item for item in replay["results"] if item.get("status") == "signal"
    ]
    if not replay_signals:
        raise ValueError("The latest replay contains no valid signals.")
    metadata = _universe_metadata()
    benchmark_path = CACHE_ROOT / replay_date / "SPY.csv"
    benchmark = _load_history(benchmark_path, replay_date)
    strategy = strategy_registry.require_usable("swing_trading")
    PUBLIC_CHART_ROOT.mkdir(parents=True, exist_ok=True)
    evidence_items: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    missing_raw_data: list[str] = []

    for item in replay_signals:
        ticker = str(item["ticker"])
        history_path = CACHE_ROOT / replay_date / f"{ticker}.csv"
        try:
            history = _load_history(history_path, replay_date)
        except (FileNotFoundError, ValueError):
            missing_raw_data.append(ticker)
            continue
        close = pd.to_numeric(history["Close"], errors="raise")
        ema20_series = close.ewm(span=20, adjust=False).mean()
        ema50_series = close.ewm(span=50, adjust=False).mean()
        stored = item["production_signal"]
        recalculated = strategy.scan(
            ticker=ticker,
            history=history,
            benchmark=benchmark,
            signal_timestamp=stored["signal_timestamp"],
        )
        if recalculated is None:
            mismatches.append(
                {"ticker": ticker, "fields": ["signal unexpectedly rejected"]}
            )
            continue
        fields = [
            field
            for field in COMPARISON_FIELDS
            if not _close(stored.get(field), recalculated.get(field))
        ]
        diagnostics = item["diagnostics"]
        expected_fill = float(recalculated["expected_entry_fill"])
        stop = float(recalculated["stop_loss"])
        risk_per_share = expected_fill - stop
        risk_percent = risk_per_share / expected_fill * 100
        levels = {
            "ema20": round(float(ema20_series.iloc[-1]), 6),
            "ema50": round(float(ema50_series.iloc[-1]), 6),
            "pullback_entry": float(recalculated["proposed_pullback_entry"]),
            "swing_low": float(diagnostics["swing_low_20"]),
            "stop": stop,
            "tp1": float(recalculated["target_1"]),
            "tp2": float(recalculated["target_2"]),
        }
        checks = {
            "raw_signal_candle_present": history.index[-1].date().isoformat()
            == replay_date,
            "no_lookahead_data": bool(
                (history.index <= pd.Timestamp(replay_date)).all()
            ),
            "stored_signal_matches_recalculation": not fields,
            "signal_price_matches_close": _close(
                recalculated["signal_price"], float(close.iloc[-1])
            ),
            "ema20_matches_pullback_entry": _close(
                levels["ema20"], levels["pullback_entry"]
            ),
            "ema20_matches_replay_ledger": _close(
                levels["ema20"], float(diagnostics["ema20"])
            ),
            "swing_low_matches_raw_20_day_low": _close(
                levels["swing_low"],
                float(pd.to_numeric(history["Low"], errors="raise").tail(20).min()),
            ),
            "risk_within_five_percent": risk_percent <= MAX_RISK_PCT * 100 + 1e-9,
            "risk_percent_matches_replay_ledger": _close(
                risk_percent,
                float(diagnostics["risk_percent"]),
                tolerance=1e-5,
            ),
            "rr_target_1_is_two": _close(
                (levels["tp1"] - expected_fill) / risk_per_share,
                2.0,
                tolerance=1e-5,
            ),
            "rr_target_2_is_four": _close(
                (levels["tp2"] - expected_fill) / risk_per_share,
                4.0,
                tolerance=1e-5,
            ),
            "qualification_reasons_present": bool(item.get("reasons")),
        }
        if fields:
            mismatches.append({"ticker": ticker, "fields": fields})
        company = metadata.get(
            ticker, {"company_name": ticker, "sector": "Unclassified"}
        )
        evidence = {
            "id": f"LS-{replay_date}-{ticker}",
            "ticker": ticker,
            **company,
            "signal_date": replay_date,
            "data_timestamp": recalculated["data_timestamp"],
            "signal_timestamp": recalculated["signal_timestamp"],
            "market_regime": recalculated["market_regime"],
            "market_regime_score": float(recalculated["market_regime_score"]),
            "signal_price": float(recalculated["signal_price"]),
            "confidence": float(recalculated["confidence"]),
            "risk_percent": round(risk_percent, 6),
            "risk_reward_target_1": 2.0,
            "risk_reward_target_2": 4.0,
            "levels": levels,
            "qualification_reasons": list(item["reasons"]),
            "strategy_version": recalculated["strategy_version"],
            "raw_ohlcv": {
                "file": str(history_path.relative_to(ROOT)),
                "sha256": _sha256(history_path),
                "rows": len(history),
                "first_date": history.index[0].date().isoformat(),
                "last_date": history.index[-1].date().isoformat(),
            },
            "checks": checks,
        }
        evidence["chart"] = _render_chart(
            evidence, history, ema20_series, ema50_series
        )
        evidence["checks"]["chart_values_match_ledger"] = all(
            _close(evidence["chart"]["values"][key], value)
            for key, value in {
                "signal-price": evidence["signal_price"],
                "ema20": levels["ema20"],
                "ema50": levels["ema50"],
                "pullback-entry": levels["pullback_entry"],
                "swing-low": levels["swing_low"],
                "stop": levels["stop"],
                "tp1": levels["tp1"],
                "tp2": levels["tp2"],
                "risk-percent": evidence["risk_percent"],
                "signal-date": evidence["signal_date"],
            }.items()
        )
        evidence_items.append(evidence)

    tickers = [item["ticker"] for item in evidence_items]
    duplicate_signals = sorted(
        ticker for ticker in set(tickers) if tickers.count(ticker) > 1
    )
    check_results = {
        "expected_signal_count": len(replay_signals) == 12,
        "all_signals_audited": len(evidence_items) == len(replay_signals),
        "no_missing_raw_data": not missing_raw_data,
        "no_recalculation_mismatches": not mismatches,
        "no_signal_above_five_percent_risk": all(
            item["risk_percent"] <= 5 for item in evidence_items
        ),
        "no_duplicate_signals": not duplicate_signals,
        "all_chart_values_match_ledger": all(
            item["checks"]["chart_values_match_ledger"]
            for item in evidence_items
        ),
        "all_signal_checks_passed": all(
            all(item["checks"].values()) for item in evidence_items
        ),
    }
    result = {
        "schema_version": 1,
        "generated_at": replay["generated_at"],
        "classification": "latest_complete_sp500_production_path_replay",
        "replay_date": replay_date,
        "strategy": {
            "name": "Regime-Gated Pullback",
            "version": STRATEGY_VERSION,
            "status": "FORWARD_VALIDATION",
            "asset_class": "US stocks",
        },
        "methodology": {
            "source": "Latest complete S&P 500 production-path replay",
            "execution": "Frozen strategy signal generated after the completed daily candle",
            "notice": "Replay signal evidence only. Not a live-money recommendation. Paper-trading and forward-validation use only.",
            "look_ahead_data_used": False,
        },
        "signal_count": len(evidence_items),
        "sectors": sorted({item["sector"] for item in evidence_items}),
        "tickers": tickers,
        "missing_raw_data": missing_raw_data,
        "mismatches": mismatches,
        "duplicate_signals": duplicate_signals,
        "checks": check_results,
        "all_checks_passed": all(check_results.values()),
        "signals": evidence_items,
    }
    PUBLIC_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    ARTIFACT_PATH.write_text(serialized, encoding="utf-8")
    PUBLIC_SUMMARY_PATH.write_text(serialized, encoding="utf-8")
    return result


def main() -> int:
    result = generate_latest_signal_evidence()
    print(
        json.dumps(
            {
                "signals_audited": result["signal_count"],
                "mismatches": len(result["mismatches"]),
                "sectors": result["sectors"],
                "all_checks_passed": result["all_checks_passed"],
            },
            indent=2,
        )
    )
    return 0 if result["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
