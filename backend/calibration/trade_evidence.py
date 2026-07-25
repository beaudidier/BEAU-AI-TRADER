"""Generate an auditable historical evidence pack for the frozen swing strategy.

This module is research-only. It reads the locked holdout ledger and cached raw
OHLCV, recomputes every selected example with signal-time data, and writes
lightweight evidence artifacts. It does not alter production strategy logic.
"""

from __future__ import annotations

import hashlib
import html
import json
import math
import shutil
from pathlib import Path
from typing import Any

import pandas as pd

from atr import add_atr
from backtesting.execution import entry_fill_price, exit_fill_price, simulate_long_trade
from engines.institutional_engine import calculate_institutional_analysis
from strategies.swing_strategy import (
    ENTRY_WAIT,
    MAX_HOLDING_DAYS,
    MAX_RISK_PCT,
    SLIPPAGE_BPS,
    STOP_ATR,
    STRATEGY_VERSION,
    TARGET_1_R,
    TARGET_2_R,
    TP1_PORTION,
    TRANSACTION_COST_BPS,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = ROOT / "artifacts" / "locked_holdout_dataset"
SOURCE_LEDGER = ROOT / "artifacts" / "locked_holdout_trades.csv"
EVIDENCE_DIR = ROOT / "artifacts" / "trade_evidence"
RAW_DIR = EVIDENCE_DIR / "raw"
SUMMARY_PATH = ROOT / "artifacts" / "trade_evidence_summary.json"
REPORT_PATH = ROOT / "docs" / "HISTORICAL_TRADE_EVIDENCE.md"
SELECTED_LEDGER_PATH = EVIDENCE_DIR / "selected_trade_ledger.json"

ACCOUNT_SIZE_GBP = 10_000.0
RISK_PERCENT = 1.0
RISK_BUDGET_GBP = ACCOUNT_SIZE_GBP * RISK_PERCENT / 100

COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "ABBV": "AbbVie Inc.",
    "ABT": "Abbott Laboratories",
    "AEP": "American Electric Power Company, Inc.",
    "BA": "The Boeing Company",
    "BAC": "Bank of America Corporation",
    "BLK": "BlackRock, Inc.",
    "CHTR": "Charter Communications, Inc.",
    "CL": "Colgate-Palmolive Company",
    "COP": "ConocoPhillips",
    "COST": "Costco Wholesale Corporation",
    "DUK": "Duke Energy Corporation",
    "IBM": "International Business Machines Corporation",
    "ITW": "Illinois Tool Works Inc.",
    "JNJ": "Johnson & Johnson",
    "KO": "The Coca-Cola Company",
    "LOW": "Lowe's Companies, Inc.",
    "MRK": "Merck & Co., Inc.",
    "NEM": "Newmont Corporation",
    "ORCL": "Oracle Corporation",
    "PSA": "Public Storage",
    "SBUX": "Starbucks Corporation",
    "TMO": "Thermo Fisher Scientific Inc.",
    "VZ": "Verizon Communications Inc.",
    "WELL": "Welltower Inc.",
    "XOM": "Exxon Mobil Corporation",
}

SELECTIONS = (
    # Ten wins across five years, eight sectors, and Bull/Sideways conditions.
    {"category": "WINNER", "trade_id": "existing_market_regime-ORCL-2017-05-10"},
    {"category": "WINNER", "trade_id": "existing_market_regime-TMO-2017-04-19"},
    {"category": "WINNER", "trade_id": "existing_market_regime-LOW-2018-08-06"},
    {"category": "WINNER", "trade_id": "existing_market_regime-BLK-2018-01-02"},
    {"category": "WINNER", "trade_id": "existing_market_regime-COST-2019-02-08"},
    {"category": "WINNER", "trade_id": "existing_market_regime-WELL-2019-02-22"},
    {"category": "WINNER", "trade_id": "existing_market_regime-NEM-2020-02-13"},
    {"category": "WINNER", "trade_id": "existing_market_regime-ABT-2020-08-18"},
    {"category": "WINNER", "trade_id": "existing_market_regime-PSA-2021-05-17"},
    {"category": "WINNER", "trade_id": "existing_market_regime-DUK-2021-04-30"},
    # Ten losses across five years, eight sectors, and Bull/Bear/Sideways conditions.
    {"category": "LOSER", "trade_id": "existing_market_regime-CL-2017-04-19"},
    {"category": "LOSER", "trade_id": "existing_market_regime-XOM-2017-07-19"},
    {"category": "LOSER", "trade_id": "existing_market_regime-SBUX-2018-06-04"},
    {"category": "LOSER", "trade_id": "existing_market_regime-JNJ-2018-10-03"},
    {"category": "LOSER", "trade_id": "existing_market_regime-KO-2019-01-28"},
    {"category": "LOSER", "trade_id": "existing_market_regime-BAC-2019-02-13"},
    {"category": "LOSER", "trade_id": "existing_market_regime-ITW-2020-01-14"},
    {"category": "LOSER", "trade_id": "existing_market_regime-IBM-2020-08-31"},
    {"category": "LOSER", "trade_id": "existing_market_regime-MRK-2021-04-12"},
    {"category": "LOSER", "trade_id": "existing_market_regime-VZ-2021-01-04"},
    # Five entry limits that expired without a fill.
    {"category": "EXPIRED", "ticker": "BA", "signal_date": "2017-04-19", "reason": "Pullback limit was not traded within 3 candles"},
    {"category": "EXPIRED", "ticker": "COP", "signal_date": "2018-01-02", "reason": "Pullback limit was not traded within 3 candles"},
    {"category": "EXPIRED", "ticker": "CHTR", "signal_date": "2019-01-18", "reason": "Pullback limit was not traded within 3 candles"},
    {"category": "EXPIRED", "ticker": "AEP", "signal_date": "2020-01-27", "reason": "Pullback limit was not traded within 3 candles"},
    {"category": "EXPIRED", "ticker": "ABBV", "signal_date": "2021-01-06", "reason": "Pullback limit was not traded within 3 candles"},
    # Five hard rejections spanning all holdout years and three rejection paths.
    {"category": "REJECTED", "ticker": "AAPL", "signal_date": "2017-06-22", "reason": "Position risk exceeds 5% of entry price"},
    {"category": "REJECTED", "ticker": "XOM", "signal_date": "2018-04-02", "reason": "Market regime filter disallowed long entry"},
    {"category": "REJECTED", "ticker": "BAC", "signal_date": "2019-02-14", "reason": "Overlapping position for ticker"},
    {"category": "REJECTED", "ticker": "ABBV", "signal_date": "2020-04-29", "reason": "Position risk exceeds 5% of entry price"},
    {"category": "REJECTED", "ticker": "ABBV", "signal_date": "2021-03-04", "reason": "Market regime filter disallowed long entry"},
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 8)
    return value


def _close(left: Any, right: Any, tolerance: float = 1e-6) -> bool:
    try:
        return math.isclose(float(left), float(right), rel_tol=1e-8, abs_tol=tolerance)
    except (TypeError, ValueError):
        return False


def _load_history(ticker: str) -> pd.DataFrame:
    path = DATASET_DIR / f"{ticker}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing locked holdout history for {ticker}.")
    data = pd.read_csv(path, index_col=0, parse_dates=True)
    required = {"Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(data.columns) or data.index.has_duplicates or not data.index.is_monotonic_increasing:
        raise ValueError(f"Invalid locked holdout history for {ticker}.")
    return data


def _position_size(entry: float, stop: float) -> dict[str, Any]:
    risk_per_share = entry - stop
    risk_limited = math.floor(RISK_BUDGET_GBP / risk_per_share) if risk_per_share > 0 else 0
    cash_limited = math.floor(ACCOUNT_SIZE_GBP / entry) if entry > 0 else 0
    shares = max(0, min(risk_limited, cash_limited))
    return {
        "account_size_gbp": ACCOUNT_SIZE_GBP,
        "risk_percent": RISK_PERCENT,
        "risk_budget_gbp": RISK_BUDGET_GBP,
        "risk_per_share": risk_per_share,
        "risk_limited_shares": risk_limited,
        "cash_limited_shares": cash_limited,
        "position_size_shares": shares,
        "total_position_value_gbp": shares * entry,
        "maximum_monetary_risk_gbp": shares * risk_per_share,
    }


def _match_source_rows(ledger: pd.DataFrame, selection: dict[str, str]) -> pd.DataFrame:
    if "trade_id" in selection:
        rows = ledger.loc[ledger["trade_id"] == selection["trade_id"]].copy()
        rows = rows.sort_values("leg_number")
    else:
        rows = ledger.loc[
            (ledger["ticker"] == selection["ticker"])
            & (ledger["signal_date"] == selection["signal_date"])
            & (ledger["reason"] == selection["reason"])
        ].copy()
    if rows.empty:
        raise ValueError(f"Selected ledger record was not found: {selection}")
    if "trade_id" not in selection and len(rows) != 1:
        raise ValueError(f"Selected non-trade record is not unique: {selection}")
    return rows


def _reference_price(leg: dict[str, Any], data: pd.DataFrame, levels: dict[str, float]) -> float:
    if leg["leg"] == "TP1":
        return levels["target_1"]
    if leg["leg"] == "TP2":
        return levels["target_2"]
    if leg["leg"] == "STOP":
        return levels["stop_loss"]
    return float(data.iloc[int(leg["exit_index"])]["Close"])


def _enrich_execution(
    outcome: dict[str, Any],
    data: pd.DataFrame,
    levels: dict[str, float],
    position_size: int,
) -> dict[str, Any]:
    legs = []
    exit_slippage = 0.0
    for source in outcome["exit_legs"]:
        leg = dict(source)
        reference = _reference_price(leg, data, levels)
        quantity = int(leg["shares"])
        leg["exit_date"] = str(data.index[int(leg["exit_index"])].date())
        leg["reference_price"] = reference
        leg["slippage_per_share"] = reference - float(leg["exit_price"])
        leg["slippage_amount_gbp"] = leg["slippage_per_share"] * quantity
        exit_slippage += leg["slippage_amount_gbp"]
        legs.append(_clean(leg))
    entry_slippage = (levels["expected_entry_fill"] - levels["proposed_pullback_entry"]) * position_size
    return {
        "holding_period_candles": int(outcome["holding_days"]),
        "exit_legs": legs,
        "entry_transaction_cost_gbp": outcome["entry_transaction_cost"],
        "total_transaction_cost_gbp": outcome["total_transaction_cost"],
        "entry_slippage_gbp": entry_slippage,
        "exit_slippage_gbp": exit_slippage,
        "total_slippage_gbp": entry_slippage + exit_slippage,
        "total_pnl_gbp": outcome["total_pnl"],
        "final_r_result": outcome["r_multiple"],
        "maximum_favourable_excursion_r": outcome["mfe_r"],
        "maximum_adverse_excursion_r": outcome["mae_r"],
        "tp1_hit": bool(outcome["tp1_hit"]),
        "tp2_hit": bool(outcome["tp2_hit"]),
        "stop_hit": bool(outcome["stop_hit"]),
    }


def _qualification_reasons(
    category: str,
    source: dict[str, Any],
    market_score: float,
    levels: dict[str, float],
    signal_date: str,
    touch_date: str | None,
    touch_session: int | None,
    overlap_trade_id: str | None,
) -> list[str]:
    risk_pct = (levels["risk_per_share"] / levels["expected_entry_fill"]) * 100
    reasons = [
        f"Signal calculations used completed daily candles ending {signal_date}; no later candle was supplied to the analysis engines.",
        f"Signal-time EMA20 was {levels['proposed_pullback_entry']:.6f}; the frozen entry window was {ENTRY_WAIT} completed sessions.",
        f"Signal-time ATR was {levels['atr']:.6f} and the 20-session swing low was {levels['swing_low_20']:.6f}.",
    ]
    allowed = bool(source["existing_market_regime"])
    comparator = "met" if allowed else "failed"
    reasons.append(f"Institutional market-regime score {market_score:.0f} {comparator} the frozen >=65 long-entry gate.")
    if category in {"WINNER", "LOSER"}:
        reasons.extend(
            (
                f"The EMA20 limit traded on {touch_date}, session {touch_session} of {ENTRY_WAIT}.",
                f"Stop {levels['stop_loss']:.6f} was below executable fill {levels['expected_entry_fill']:.6f}.",
                f"Per-share risk was {risk_pct:.4f}% of entry, within the frozen 5% maximum.",
                "No same-ticker position overlapped this accepted entry.",
            )
        )
    elif category == "EXPIRED":
        reasons.append(f"None of the next {ENTRY_WAIT} raw candles traded through the EMA20 limit; no position was opened.")
    elif source["reason"] == "Position risk exceeds 5% of entry price":
        reasons.append(f"Per-share risk was {risk_pct:.4f}% of entry, above the frozen 5% maximum; no position was opened.")
    elif source["reason"] == "Market regime filter disallowed long entry":
        reasons.append("The market-regime gate failed before an entry could be activated; no position was opened.")
    elif source["reason"] == "Overlapping position for ticker":
        reasons.append(f"Existing position {overlap_trade_id or 'for this ticker'} was still active; the candidate was not evaluated as a new entry.")
    return reasons


def _svg_chart(example: dict[str, Any], data: pd.DataFrame, path: Path) -> dict[str, Any]:
    signal_position = data.index.get_loc(pd.Timestamp(example["signal_date"]))
    if example["actual_entry_date"]:
        end_anchor = data.index.get_loc(pd.Timestamp(example["exit_legs"][-1]["exit_date"]))
    else:
        end_anchor = min(len(data) - 1, signal_position + ENTRY_WAIT + 25)
    start = max(0, signal_position - 50)
    end = min(len(data) - 1, end_anchor + 5)
    window = data.iloc[start:end + 1].copy()
    close = pd.to_numeric(data["Close"], errors="coerce")
    ema20 = close.ewm(span=20, adjust=False).mean().iloc[start:end + 1]
    ema50 = close.ewm(span=50, adjust=False).mean().iloc[start:end + 1]
    levels = example["levels"]

    width, height = 1200, 680
    left, right, top, bottom = 72, 1120, 92, 594
    prices = list(window["Low"]) + list(window["High"]) + [
        levels["proposed_pullback_entry"],
        levels["swing_low_20"],
        levels["stop_loss"],
        levels["target_1"],
        levels["target_2"],
    ]
    minimum, maximum = min(prices), max(prices)
    padding = max((maximum - minimum) * 0.06, maximum * 0.005)
    minimum, maximum = minimum - padding, maximum + padding
    count = len(window)

    def x(position: int) -> float:
        return left + (right - left) * position / max(1, count - 1)

    def y(price: float) -> float:
        return bottom - (float(price) - minimum) / (maximum - minimum) * (bottom - top)

    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" '
            f'data-entry="{levels["expected_entry_fill"]:.8f}" data-stop="{levels["stop_loss"]:.8f}" '
            f'data-target-1="{levels["target_1"]:.8f}" data-target-2="{levels["target_2"]:.8f}" '
            f'data-swing-low="{levels["swing_low_20"]:.8f}" data-signal-timestamp="{html.escape(example["data_timestamp"])}">'
        ),
        f"<title>{html.escape(example['ticker'])} {html.escape(example['category'])} trade evidence</title>",
        f"<desc>Daily candles with frozen swing strategy levels for signal {html.escape(example['signal_date'])}.</desc>",
        '<rect width="1200" height="680" fill="#020617"/>',
        f'<text x="72" y="34" fill="#f8fafc" font-family="sans-serif" font-size="22" font-weight="600">{html.escape(example["ticker"])} · {html.escape(example["company_name"])} · {html.escape(example["category"])}</text>',
        f'<text x="72" y="62" fill="#94a3b8" font-family="sans-serif" font-size="14">Signal {html.escape(example["data_timestamp"])} · Regime {html.escape(example["market_regime"]["historical_label"])} · Engine score {example["market_regime"]["engine_score"]} · {html.escape(example["recommendation"])}</text>',
    ]
    for tick in range(6):
        price = minimum + (maximum - minimum) * tick / 5
        py = y(price)
        parts.append(f'<line x1="{left}" y1="{py:.2f}" x2="{right}" y2="{py:.2f}" stroke="#1e293b" stroke-width="1"/>')
        parts.append(f'<text x="{right + 10}" y="{py + 4:.2f}" fill="#64748b" font-family="monospace" font-size="11">{price:.2f}</text>')

    candle_width = max(2.0, min(8.0, (right - left) / max(1, count) * 0.62))
    for position, (_, candle) in enumerate(window.iterrows()):
        px = x(position)
        opening, high, low, closing = (float(candle[key]) for key in ("Open", "High", "Low", "Close"))
        color = "#22c55e" if closing >= opening else "#ef4444"
        body_top, body_bottom = min(y(opening), y(closing)), max(y(opening), y(closing))
        parts.append(f'<line x1="{px:.2f}" y1="{y(high):.2f}" x2="{px:.2f}" y2="{y(low):.2f}" stroke="{color}" stroke-width="1"/>')
        parts.append(f'<rect x="{px - candle_width / 2:.2f}" y="{body_top:.2f}" width="{candle_width:.2f}" height="{max(1.2, body_bottom - body_top):.2f}" fill="{color}"/>')

    def polyline(series: pd.Series, color: str) -> None:
        points = " ".join(f"{x(position):.2f},{y(float(value)):.2f}" for position, value in enumerate(series))
        parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>')

    polyline(ema20, "#f59e0b")
    polyline(ema50, "#38bdf8")
    line_specs = (
        ("Pullback entry", levels["proposed_pullback_entry"], "#22d3ee", ""),
        ("Swing low", levels["swing_low_20"], "#94a3b8", "6 4"),
        ("Stop", levels["stop_loss"], "#fb7185", ""),
        ("TP1", levels["target_1"], "#4ade80", ""),
        ("TP2", levels["target_2"], "#c084fc", ""),
    )
    for label, price, color, dash in line_specs:
        dash_attribute = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(f'<line x1="{left}" y1="{y(price):.2f}" x2="{right}" y2="{y(price):.2f}" stroke="{color}" stroke-width="1.5"{dash_attribute}/>')
        parts.append(f'<text x="{left + 6}" y="{y(price) - 5:.2f}" fill="{color}" font-family="sans-serif" font-size="11">{label} {price:.2f}</text>')

    signal_local = signal_position - start
    signal_x = x(signal_local)
    signal_y = y(float(data.iloc[signal_position]["Close"]))
    parts.append(f'<line x1="{signal_x:.2f}" y1="{top}" x2="{signal_x:.2f}" y2="{bottom}" stroke="#e2e8f0" stroke-width="1" stroke-dasharray="3 4"/>')
    parts.append(f'<circle cx="{signal_x:.2f}" cy="{signal_y:.2f}" r="5" fill="#f8fafc"/>')
    parts.append(f'<text x="{signal_x + 7:.2f}" y="{top + 15}" fill="#e2e8f0" font-family="sans-serif" font-size="11">Signal</text>')

    entry_marker = None
    if example["actual_entry_date"]:
        entry_position = data.index.get_loc(pd.Timestamp(example["actual_entry_date"])) - start
        entry_x, entry_y = x(entry_position), y(float(example["actual_entry_price"]))
        parts.append(f'<polygon points="{entry_x:.2f},{entry_y - 10:.2f} {entry_x - 8:.2f},{entry_y + 6:.2f} {entry_x + 8:.2f},{entry_y + 6:.2f}" fill="#22d3ee"/>')
        parts.append(f'<text x="{entry_x + 9:.2f}" y="{entry_y + 4:.2f}" fill="#22d3ee" font-family="sans-serif" font-size="11">Entry</text>')
        entry_marker = {"date": example["actual_entry_date"], "price": example["actual_entry_price"]}
    else:
        no_entry_y = y(levels["expected_entry_fill"])
        parts.append(f'<polygon points="{signal_x:.2f},{no_entry_y - 8:.2f} {signal_x - 8:.2f},{no_entry_y:.2f} {signal_x:.2f},{no_entry_y + 8:.2f} {signal_x + 8:.2f},{no_entry_y:.2f}" fill="none" stroke="#fbbf24" stroke-width="2"/>')
        parts.append(f'<text x="{signal_x + 10:.2f}" y="{no_entry_y + 4:.2f}" fill="#fbbf24" font-family="sans-serif" font-size="11">No entry</text>')

    exit_markers = []
    for leg in example["exit_legs"]:
        exit_position = data.index.get_loc(pd.Timestamp(leg["exit_date"])) - start
        exit_x, exit_y = x(exit_position), y(float(leg["exit_price"]))
        parts.append(f'<polygon points="{exit_x:.2f},{exit_y + 10:.2f} {exit_x - 8:.2f},{exit_y - 6:.2f} {exit_x + 8:.2f},{exit_y - 6:.2f}" fill="#f8fafc"/>')
        parts.append(f'<text x="{exit_x + 9:.2f}" y="{exit_y - 8:.2f}" fill="#f8fafc" font-family="sans-serif" font-size="11">{html.escape(leg["leg"])}</text>')
        exit_markers.append({"date": leg["exit_date"], "price": leg["exit_price"], "label": leg["leg"]})

    tick_positions = sorted({0, count - 1, *(round((count - 1) * index / 5) for index in range(1, 5))})
    for position in tick_positions:
        label = str(window.index[position].date())
        parts.append(f'<text x="{x(position):.2f}" y="{bottom + 28}" text-anchor="middle" fill="#64748b" font-family="monospace" font-size="11">{label}</text>')
    parts.extend(
        (
            '<line x1="72" y1="632" x2="96" y2="632" stroke="#f59e0b" stroke-width="2"/><text x="102" y="636" fill="#94a3b8" font-family="sans-serif" font-size="11">EMA20</text>',
            '<line x1="176" y1="632" x2="200" y2="632" stroke="#38bdf8" stroke-width="2"/><text x="206" y="636" fill="#94a3b8" font-family="sans-serif" font-size="11">EMA50</text>',
            f'<text x="1120" y="654" text-anchor="end" fill="#475569" font-family="sans-serif" font-size="11">Retrospective holdout · Out-of-sample · Not forward validation</text>',
            "</svg>",
        )
    )
    path.write_text("\n".join(parts))
    return {
        "file": f"artifacts/trade_evidence/{path.name}",
        "window_start": str(window.index[0].date()),
        "window_end": str(window.index[-1].date()),
        "lines": {
            "ema20_at_signal": example["levels"]["ema20"],
            "ema50_at_signal": example["levels"]["ema50"],
            "proposed_pullback_entry": levels["proposed_pullback_entry"],
            "swing_low_20": levels["swing_low_20"],
            "stop_loss": levels["stop_loss"],
            "target_1": levels["target_1"],
            "target_2": levels["target_2"],
        },
        "markers": {
            "signal": {"timestamp": example["data_timestamp"], "price": example["signal_price"]},
            "entry": entry_marker,
            "exits": exit_markers,
        },
    }


def _build_example(
    number: int,
    selection: dict[str, str],
    source_rows: pd.DataFrame,
    ledger_trades: pd.DataFrame,
    benchmark: pd.DataFrame,
) -> dict[str, Any]:
    source = _clean(source_rows.iloc[0].to_dict())
    ticker = str(source["ticker"])
    signal_date = str(source["signal_date"])
    category = selection["category"]
    data = _load_history(ticker)
    signal_timestamp = pd.Timestamp(signal_date)
    signal_position = data.index.get_loc(signal_timestamp)
    signal_history = data.iloc[:signal_position + 1].copy()
    benchmark_history = benchmark.loc[:signal_timestamp].copy()
    analysis = calculate_institutional_analysis(signal_history, benchmark_history)
    enriched = add_atr(signal_history)
    close = pd.to_numeric(signal_history["Close"], errors="coerce")
    ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
    ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
    atr = float(enriched["ATR"].iloc[-1])
    swing_low = float(signal_history.tail(20)["Low"].min())
    expected_fill = entry_fill_price(ema20, SLIPPAGE_BPS)
    stop = swing_low - STOP_ATR * atr
    risk = expected_fill - stop
    target_1 = expected_fill + TARGET_1_R * risk
    target_2 = expected_fill + TARGET_2_R * risk
    levels = {
        "ema20": ema20,
        "ema50": ema50,
        "atr": atr,
        "proposed_pullback_entry": ema20,
        "expected_entry_fill": expected_fill,
        "swing_low_20": swing_low,
        "stop_loss": stop,
        "risk_per_share": risk,
        "target_1": target_1,
        "target_2": target_2,
    }
    sizing = _position_size(expected_fill, stop)
    entry_window_positions = range(signal_position + 1, min(len(data), signal_position + ENTRY_WAIT + 1))
    touch_position = next(
        (
            position
            for position in entry_window_positions
            if float(data.iloc[position]["Low"]) <= ema20 <= float(data.iloc[position]["High"])
        ),
        None,
    )
    touch_date = str(data.index[touch_position].date()) if touch_position is not None else None
    touch_session = touch_position - signal_position if touch_position is not None else None
    overlap_trade_id = None
    if source.get("reason") == "Overlapping position for ticker":
        active = ledger_trades.loc[
            (ledger_trades["ticker"] == ticker)
            & (pd.to_datetime(ledger_trades["entry_date"]) <= signal_timestamp)
            & (pd.to_datetime(ledger_trades["exit_date"]) >= signal_timestamp)
        ]
        if not active.empty:
            overlap_trade_id = str(active.iloc[-1]["trade_id"])

    market_engine = analysis["engines"]["market_regime"]
    classification = {
        "retrospective_holdout": True,
        "out_of_sample": True,
        "forward_validation": False,
        "label": "RETROSPECTIVE HOLDOUT · OUT-OF-SAMPLE · NOT FORWARD VALIDATION",
    }
    example = {
        "id": f"E{number:02d}",
        "category": category,
        "ticker": ticker,
        "company_name": COMPANY_NAMES[ticker],
        "sector": str(source["sector"]),
        "classification": classification,
        "strategy_id": "swing_trading",
        "strategy_version": STRATEGY_VERSION,
        "signal_date": signal_date,
        "data_timestamp": data.index[signal_position].isoformat(),
        "analysis_input": {
            "start": data.index[0].isoformat(),
            "end": data.index[signal_position].isoformat(),
            "rows": len(signal_history),
            "benchmark_end": benchmark_history.index[-1].isoformat(),
            "later_candles_supplied": False,
        },
        "market_regime": {
            "historical_label": str(source["market_regime"]),
            "engine_score": float(market_engine["score"]),
            "engine_explanation": str(market_engine["explanation"]),
        },
        "confidence": float(analysis["overall_score"]),
        "recommendation": str(analysis["recommendation"]),
        "engine_scores": {name: float(result["score"]) for name, result in analysis["engines"].items()},
        "engine_explanations": {name: str(result["explanation"]) for name, result in analysis["engines"].items()},
        "signal_price": float(data.iloc[signal_position]["Close"]),
        "levels": levels,
        "actual_entry_date": str(source["entry_date"]) if category in {"WINNER", "LOSER"} else None,
        "actual_entry_price": float(source["entry_price"]) if category in {"WINNER", "LOSER"} else None,
        "candidate_touch_date": touch_date,
        "candidate_touch_session": touch_session,
        "position_sizing": sizing,
        "rejection_or_expiry_reason": str(source["reason"]) if category in {"REJECTED", "EXPIRED"} else None,
        "overlap_trade_id": overlap_trade_id,
        "holding_period_candles": 0,
        "exit_legs": [],
        "costs_and_slippage": {
            "entry_transaction_cost_gbp": 0.0,
            "total_transaction_cost_gbp": 0.0,
            "entry_slippage_gbp": 0.0,
            "exit_slippage_gbp": 0.0,
            "total_slippage_gbp": 0.0,
        },
        "final_r_result": None,
        "source_ledger_r": float(source["r_multiple"]) if category in {"WINNER", "LOSER"} else None,
        "maximum_favourable_excursion_r": None,
        "maximum_adverse_excursion_r": None,
        "exact_qualification_reasons": _qualification_reasons(
            category,
            source,
            float(market_engine["score"]),
            levels,
            signal_date,
            touch_date,
            touch_session,
            overlap_trade_id,
        ),
        "source": {
            "raw_ohlcv": f"artifacts/trade_evidence/raw/{ticker}.csv",
            "raw_ohlcv_sha256": _sha256(DATASET_DIR / f"{ticker}.csv"),
            "selected_ledger": "artifacts/trade_evidence/selected_trade_ledger.json",
            "source_trade_id": str(source["trade_id"]) if source.get("trade_id") else None,
        },
    }

    audit_checks = {
        "signal_date_exists_in_raw_ohlcv": signal_timestamp in data.index,
        "analysis_ends_at_signal_timestamp": signal_history.index[-1] == signal_timestamp,
        "benchmark_ends_no_later_than_signal": benchmark_history.index[-1] <= signal_timestamp,
        "ema20_matches_source_ledger": _close(ema20, source["ema20"]),
        "atr_matches_source_ledger": _close(atr, source["atr"]),
        "swing_low_matches_source_ledger": _close(swing_low, source["swing_low_20"]),
        "market_regime_gate_matches_source_ledger": (float(market_engine["score"]) >= 65) == bool(source["existing_market_regime"]),
    }

    if category in {"WINNER", "LOSER"}:
        entry_position = data.index.get_loc(pd.Timestamp(example["actual_entry_date"]))
        if sizing["position_size_shares"] <= 0:
            raise ValueError(f"Selected trade has zero £10,000-account position size: {selection}")
        normalized = simulate_long_trade(
            data,
            entry_position,
            expected_fill,
            stop,
            target_1,
            target_2,
            shares=100,
            max_holding_days=MAX_HOLDING_DAYS,
            slippage_bps=SLIPPAGE_BPS,
            transaction_cost_bps=TRANSACTION_COST_BPS,
        )
        sized = simulate_long_trade(
            data,
            entry_position,
            expected_fill,
            stop,
            target_1,
            target_2,
            shares=sizing["position_size_shares"],
            max_holding_days=MAX_HOLDING_DAYS,
            slippage_bps=SLIPPAGE_BPS,
            transaction_cost_bps=TRANSACTION_COST_BPS,
        )
        if normalized is None or sized is None:
            raise ValueError(f"Selected trade could not be replayed: {selection}")
        execution = _enrich_execution(sized, data, levels, sizing["position_size_shares"])
        example["holding_period_candles"] = execution["holding_period_candles"]
        example["exit_legs"] = execution["exit_legs"]
        example["costs_and_slippage"] = {
            key: execution[key]
            for key in (
                "entry_transaction_cost_gbp",
                "total_transaction_cost_gbp",
                "entry_slippage_gbp",
                "exit_slippage_gbp",
                "total_slippage_gbp",
            )
        }
        example["total_pnl_gbp"] = execution["total_pnl_gbp"]
        example["final_r_result"] = execution["final_r_result"]
        example["maximum_favourable_excursion_r"] = execution["maximum_favourable_excursion_r"]
        example["maximum_adverse_excursion_r"] = execution["maximum_adverse_excursion_r"]
        source_leg_rows = source_rows.sort_values("leg_number")
        normalized_legs = normalized["exit_legs"]
        audit_checks.update(
            {
                "entry_date_is_within_three_session_window": 1 <= entry_position - signal_position <= ENTRY_WAIT,
                "entry_candle_traded_through_signal_ema20": float(data.iloc[entry_position]["Low"]) <= ema20 <= float(data.iloc[entry_position]["High"]),
                "entry_price_matches_source_ledger": _close(expected_fill, source["entry_price"]),
                "stop_matches_source_ledger": _close(stop, source["stop_loss"]),
                "target_1_matches_source_ledger": _close(target_1, source["target_1"]),
                "target_2_matches_source_ledger": _close(target_2, source["target_2"]),
                "exit_leg_count_matches_source_ledger": len(normalized_legs) == len(source_leg_rows),
                "exit_indices_match_source_ledger": all(
                    int(leg["exit_index"]) == int(row["leg_exit_index"])
                    for leg, (_, row) in zip(normalized_legs, source_leg_rows.iterrows(), strict=True)
                ),
                "exit_dates_match_raw_candles": all(
                    str(data.index[int(leg["exit_index"])].date())
                    == str(data.index[int(row["leg_exit_index"])].date())
                    for leg, (_, row) in zip(normalized_legs, source_leg_rows.iterrows(), strict=True)
                ),
                "exit_prices_match_source_ledger": all(
                    _close(leg["exit_price"], row["leg_exit_price"])
                    for leg, (_, row) in zip(normalized_legs, source_leg_rows.iterrows(), strict=True)
                ),
                "normalized_r_matches_source_ledger": _close(normalized["r_multiple"], source["r_multiple"]),
                "category_matches_recomputed_result": (execution["final_r_result"] > 0) == (category == "WINNER"),
            }
        )
    else:
        example["total_pnl_gbp"] = 0.0
        audit_checks.update(
            {
                "actual_entry_date_is_null": example["actual_entry_date"] is None,
                "actual_entry_price_is_null": example["actual_entry_price"] is None,
                "no_exit_legs_exist": not example["exit_legs"],
                "no_costs_or_slippage_charged": all(value == 0 for value in example["costs_and_slippage"].values()),
                "expiry_window_contains_no_fill": category != "EXPIRED" or touch_position is None,
                "exact_non_entry_reason_matches_source_ledger": example["rejection_or_expiry_reason"] == source["reason"],
            }
        )

    if not all(audit_checks.values()):
        failed = [name for name, passed in audit_checks.items() if not passed]
        raise AssertionError(f"Evidence audit failed for {selection}: {failed}")
    example["audit_checks"] = audit_checks
    chart_name = f"{example['id'].lower()}-{category.lower()}-{ticker.lower()}-{signal_date}.svg"
    example["chart"] = _svg_chart(example, data, EVIDENCE_DIR / chart_name)
    return _clean(example)


def _write_report(summary: dict[str, Any]) -> None:
    distribution = summary["distribution"]
    lines = [
        "# Historical Trade Evidence Pack",
        "",
        "## Scope and limitations",
        "",
        "This pack contains transparent examples from the frozen Regime-Gated Pullback swing strategy. Every example is a **retrospective holdout** and **out-of-sample** observation from the unused 2016-07-01 through 2021-07-10 window. None is a live forward-validation trade.",
        "",
        "**These examples do not guarantee future profitability.** They show how fixed rules behaved on selected historical candles after costs and slippage.",
        "",
        f"- Strategy version: `{summary['strategy']['version']}`",
        f"- Examples: {summary['example_count']} ({distribution['WINNER']} winners, {distribution['LOSER']} losers, {distribution['EXPIRED']} expired signals, {distribution['REJECTED']} rejected candidates)",
        f"- Sectors covered: {', '.join(summary['coverage']['sectors'])}",
        f"- Historical regimes covered: {', '.join(summary['coverage']['market_regimes'])}",
        f"- Signal years covered: {', '.join(str(year) for year in summary['coverage']['years'])}",
        "- Account illustration: £10,000 cash account with a 1% (£100) maximum risk budget; whole shares only and no leverage.",
        "- Currency assumption: historical US price units are treated as GBP-equivalent for the requested sizing illustration; no historical USD/GBP conversion is applied.",
        "- Execution: 5 bps adverse entry/exit slippage, 5 bps transaction cost per side, 50% at TP1, original stop retained, and stop-first same-candle handling.",
        "- The source holdout ledger normalizes trades to 100 shares. Monetary legs below replay the requested account size; odd whole-share splits can therefore produce a small R difference while dates, levels, and fills remain identical.",
        "",
        "## Audit method",
        "",
        "For each signal, the analysis engines receive only stock and SPY candles timestamped at or before the signal close. The EMA20, EMA50, ATR, swing low, entry, stop, targets, position size, execution legs, costs, R result, MFE, and MAE are recomputed from bundled raw OHLCV. Executed examples are reconciled to the locked source ledger; expired and rejected examples are verified to contain no entry or exit.",
        "",
        "The raw snapshots are stored in `artifacts/trade_evidence/raw/`, the selected source rows in `artifacts/trade_evidence/selected_trade_ledger.json`, and the full machine-readable audit in `artifacts/trade_evidence_summary.json`.",
        "",
        "## Evidence index",
        "",
        "| ID | Outcome | Ticker | Sector | Signal | Regime | Confidence | Recommendation | Final R |",
        "| --- | --- | --- | --- | --- | --- | ---: | --- | ---: |",
    ]
    for example in summary["examples"]:
        final_r = "—" if example["final_r_result"] is None else f"{example['final_r_result']:.4f}R"
        lines.append(
            f"| [{example['id']}](#{example['id'].lower()}-{example['category'].lower()}-{example['ticker'].lower()}) "
            f"| {example['category']} | {example['ticker']} | {example['sector']} | {example['signal_date']} "
            f"| {example['market_regime']['historical_label']} | {example['confidence']:.0f} | {example['recommendation']} | {final_r} |"
        )
    for example in summary["examples"]:
        levels = example["levels"]
        sizing = example["position_sizing"]
        costs = example["costs_and_slippage"]
        lines.extend(
            (
                "",
                f"## {example['id']} {example['category'].title()}: {example['ticker']}",
                "",
                f"**{example['company_name']} · {example['sector']}**",
                "",
                f"**Classification:** {example['classification']['label']}",
                "",
                f"![{example['ticker']} {example['category'].lower()} evidence chart](../{example['chart']['file']})",
                "",
                "| Field | Audited value |",
                "| --- | --- |",
                f"| Signal date / data timestamp | {example['signal_date']} / `{example['data_timestamp']}` |",
                f"| Market regime | {example['market_regime']['historical_label']} · engine {example['market_regime']['engine_score']:.0f} · {example['market_regime']['engine_explanation']} |",
                f"| Confidence / recommendation | {example['confidence']:.0f} / {example['recommendation']} |",
                f"| Signal price | {example['signal_price']:.6f} |",
                f"| Proposed EMA20 pullback / expected fill | {levels['proposed_pullback_entry']:.6f} / {levels['expected_entry_fill']:.6f} |",
                f"| Actual entry | {example['actual_entry_date'] or 'Not entered'} / {f'{example['actual_entry_price']:.6f}' if example['actual_entry_price'] is not None else '—'} |",
                f"| Swing low / stop | {levels['swing_low_20']:.6f} / {levels['stop_loss']:.6f} |",
                f"| TP1 / TP2 | {levels['target_1']:.6f} / {levels['target_2']:.6f} |",
                f"| £10,000 position size | {sizing['position_size_shares']} shares · £{sizing['total_position_value_gbp']:.2f} value |",
                f"| Maximum monetary risk | £{sizing['maximum_monetary_risk_gbp']:.2f} of £{sizing['risk_budget_gbp']:.2f} budget |",
                f"| Holding period | {example['holding_period_candles']} completed candles |",
                f"| Costs / slippage | £{costs['total_transaction_cost_gbp']:.2f} / £{costs['total_slippage_gbp']:.2f} |",
                f"| Final result / normalized source ledger | {f'{example['final_r_result']:.6f}R / £{example['total_pnl_gbp']:.2f} / {example['source_ledger_r']:.6f}R' if example['final_r_result'] is not None else 'No trade'} |",
                f"| MFE / MAE | {f'{example['maximum_favourable_excursion_r']:.6f}R / {example['maximum_adverse_excursion_r']:.6f}R' if example['maximum_favourable_excursion_r'] is not None else 'Not applicable — no entry'} |",
                f"| Rejection or expiry reason | {example['rejection_or_expiry_reason'] or 'Not applicable'} |",
                "",
                "### Qualification audit",
                "",
            )
        )
        lines.extend(f"- {reason}" for reason in example["exact_qualification_reasons"])
        lines.extend(("", "### £10,000 account exit legs", ""))
        if example["exit_legs"]:
            lines.extend(
                (
                    "| Leg | Date | Shares | Reference | Fill | Net P/L | R contribution |",
                    "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
                )
            )
            for leg in example["exit_legs"]:
                lines.append(
                    f"| {leg['leg']} | {leg['exit_date']} | {leg['shares']} | {leg['reference_price']:.6f} "
                    f"| {leg['exit_price']:.6f} | £{leg['pnl']:.2f} | {leg['r_multiple']:.6f}R |"
                )
        else:
            lines.append("No exit legs exist because no position was entered.")
        lines.extend(
            (
                "",
                f"Audit checks: **{len(example['audit_checks'])}/{len(example['audit_checks'])} passed**. "
                f"Raw source: [`{example['ticker']}.csv`](../artifacts/trade_evidence/raw/{example['ticker']}.csv).",
            )
        )
    REPORT_PATH.write_text("\n".join(lines) + "\n")


def generate_evidence_pack() -> dict[str, Any]:
    if not SOURCE_LEDGER.exists():
        raise FileNotFoundError("The locked holdout ledger is required to generate evidence.")
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.svg", "*.json"):
        for path in EVIDENCE_DIR.glob(pattern):
            path.unlink()
    for path in RAW_DIR.glob("*.csv"):
        path.unlink()

    ledger = pd.read_csv(SOURCE_LEDGER, low_memory=False)
    ledger_trades = ledger.loc[ledger["record_type"] == "TRADE"].drop_duplicates("trade_id").copy()
    benchmark = _load_history("SPY")
    selected_rows: list[dict[str, Any]] = []
    matched: list[tuple[dict[str, str], pd.DataFrame]] = []
    for number, selection in enumerate(SELECTIONS, start=1):
        rows = _match_source_rows(ledger, selection)
        matched.append((selection, rows))
        selected_rows.append(
            {
                "evidence_id": f"E{number:02d}",
                "category": selection["category"],
                "source_rows": [_clean(row) for row in rows.to_dict(orient="records")],
            }
        )
    SELECTED_LEDGER_PATH.write_text(
        json.dumps(
            {
                "source": "artifacts/locked_holdout_trades.csv",
                "source_sha256": _sha256(SOURCE_LEDGER),
                "records": selected_rows,
            },
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )

    tickers = sorted({str(rows.iloc[0]["ticker"]) for _, rows in matched})
    for ticker in [*tickers, "SPY"]:
        shutil.copyfile(DATASET_DIR / f"{ticker}.csv", RAW_DIR / f"{ticker}.csv")

    examples = [
        _build_example(number, selection, rows, ledger_trades, benchmark)
        for number, (selection, rows) in enumerate(matched, start=1)
    ]
    distribution = {
        category: sum(example["category"] == category for example in examples)
        for category in ("WINNER", "LOSER", "EXPIRED", "REJECTED")
    }
    summary = {
        "schema_version": 1,
        "strategy": {
            "id": "swing_trading",
            "name": "Regime-Gated Pullback",
            "version": STRATEGY_VERSION,
            "status": "FORWARD_VALIDATION",
            "rules": {
                "entry_wait_candles": ENTRY_WAIT,
                "entry": "Signal-time EMA20 limit with 5 bps adverse entry slippage",
                "regime_gate": "Institutional market-regime score >= 65",
                "stop": f"{STOP_ATR} ATR below signal-time 20-session swing low",
                "target_1_r": TARGET_1_R,
                "target_2_r": TARGET_2_R,
                "tp1_portion": TP1_PORTION,
                "stop_management": "Original stop remains after TP1",
                "max_holding_candles": MAX_HOLDING_DAYS,
                "max_risk_fraction_of_entry": MAX_RISK_PCT,
                "same_candle_rule": "Stop first",
                "slippage_bps_per_side": SLIPPAGE_BPS,
                "transaction_cost_bps_per_side": TRANSACTION_COST_BPS,
            },
        },
        "classification": {
            "retrospective_holdout": True,
            "out_of_sample": True,
            "forward_validation": False,
            "holdout_window": {"start": "2016-07-01", "end": "2021-07-10"},
            "research_window_overlap": False,
        },
        "position_sizing": {
            "account_size_gbp": ACCOUNT_SIZE_GBP,
            "risk_percent": RISK_PERCENT,
            "whole_shares_only": True,
            "leverage": False,
            "currency_assumption": "Historical US price units are treated as GBP-equivalent; no historical USD/GBP conversion is applied.",
        },
        "example_count": len(examples),
        "distribution": distribution,
        "coverage": {
            "sectors": sorted({example["sector"] for example in examples}),
            "market_regimes": sorted({example["market_regime"]["historical_label"] for example in examples}),
            "years": sorted({int(example["signal_date"][:4]) for example in examples}),
            "tickers": sorted({example["ticker"] for example in examples}),
        },
        "sources": {
            "selected_ledger": "artifacts/trade_evidence/selected_trade_ledger.json",
            "selected_ledger_sha256": _sha256(SELECTED_LEDGER_PATH),
            "raw_ohlcv_directory": "artifacts/trade_evidence/raw",
            "raw_files": {
                ticker: {
                    "path": f"artifacts/trade_evidence/raw/{ticker}.csv",
                    "sha256": _sha256(RAW_DIR / f"{ticker}.csv"),
                }
                for ticker in [*tickers, "SPY"]
            },
        },
        "all_audit_checks_passed": all(all(example["audit_checks"].values()) for example in examples),
        "future_profitability_guaranteed": False,
        "examples": examples,
    }
    SUMMARY_PATH.write_text(json.dumps(_clean(summary), indent=2, allow_nan=False) + "\n")
    _write_report(summary)
    return summary


if __name__ == "__main__":
    result = generate_evidence_pack()
    print(
        json.dumps(
            {
                "example_count": result["example_count"],
                "distribution": result["distribution"],
                "coverage": result["coverage"],
                "all_audit_checks_passed": result["all_audit_checks_passed"],
            },
            indent=2,
        )
    )
