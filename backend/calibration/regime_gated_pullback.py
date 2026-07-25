"""Market-regime gating experiment for the selected Pullback execution plan.

This is an isolated audit.  It reuses the cached five-year stock histories and
does not alter production scoring or trade planning.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import date, timedelta

import numpy as np
import pandas as pd

from atr import add_atr
from calibration.pullback_robustness import (
    DATASET_CACHE, MAX_RISK_PCT, MINIMUM_CANDLES, RANDOM_SEED, SYMBOLS, _history,
    _simulate, _validate,
)
from calibration.run_audit import MAX_HOLDING_DAYS, OUTPUT, SLIPPAGE_BPS, TRANSACTION_COST_BPS, WARMUP_BARS
from backtesting.execution import entry_fill_price
from engines.engine_utils import safe_float
from engines.market_regime_engine import analyze_market_regime
from providers import get_market_data_provider

BOOTSTRAP_SAMPLES = 4_000
SELECTED = {"entry_wait": 3, "stop_atr": 1.5, "target_1_r": 2.0, "target_2_r": 4.0, "tp1_portion": .5}
FILTERS = {
    "ungated": "Ungated Pullback",
    "spy_close_ema200": "A. SPY close above EMA200",
    "spy_ema50_ema200": "B. SPY EMA50 above EMA200",
    "spy_dual_ema": "C. SPY close above EMA200 and EMA50 above EMA200",
    "nasdaq_close_ema200": "D. Nasdaq 100 (QQQ) close above EMA200",
    "universe_breadth_60": "E. At least 60% of universe above EMA200",
    "existing_market_regime": "F. Existing market-regime engine",
}


def _load_cached(ticker: str) -> pd.DataFrame:
    return pd.read_csv(DATASET_CACHE / f"{ticker}.csv", index_col=0, parse_dates=True)


def _metrics(rows: list[dict], rejected: int = 0) -> dict:
    if not rows:
        return {"eligible_signals": 0, "accepted_trades": 0, "rejected_trades": rejected, "trades_per_year": 0, "expectancy": 0, "profit_factor": None, "win_rate": 0, "average_r": 0, "maximum_drawdown": 0, "tp1_rate": 0, "tp2_rate": 0, "stop_rate": 0, "expectancy_95_ci": None}
    values = np.array([row["r_multiple"] for row in rows], dtype=float)
    gains, losses = values[values > 0].sum(), -values[values < 0].sum()
    equity = np.cumsum(values); drawdown = equity - np.maximum.accumulate(np.maximum(equity, 0))
    rng = np.random.default_rng(RANDOM_SEED + len(rows))
    means = values[rng.integers(0, len(values), size=(BOOTSTRAP_SAMPLES, len(values)))].mean(axis=1)
    years = max(1, (pd.Timestamp(rows[-1]["signal_date"]) - pd.Timestamp(rows[0]["signal_date"])).days / 365.25)
    return {"eligible_signals": 0, "accepted_trades": len(rows), "rejected_trades": rejected, "trades_per_year": round(len(rows) / years, 2), "expectancy": round(float(values.mean()), 4), "profit_factor": round(float(gains / losses), 4) if losses else None, "win_rate": round(float((values > 0).mean() * 100), 2), "average_r": round(float(values.mean()), 4), "maximum_drawdown": round(float(drawdown.min()), 4), "tp1_rate": round(float(np.mean([row["tp1_hit"] for row in rows]) * 100), 2), "tp2_rate": round(float(np.mean([row["tp2_hit"] for row in rows]) * 100), 2), "stop_rate": round(float(np.mean([row["stop_hit"] for row in rows]) * 100), 2), "expectancy_95_ci": [round(float(np.percentile(means, 2.5)), 4), round(float(np.percentile(means, 97.5)), 4)]}


def _group(rows: list[dict], rejected: list[dict], field: str) -> dict:
    values = sorted({row[field] for row in rows + rejected})
    return {value: _metrics([row for row in rows if row[field] == value], sum(row[field] == value for row in rejected)) for value in values}


def _breadth(histories: dict[str, pd.DataFrame]) -> pd.Series:
    closes = pd.concat({ticker: data["Close"] for ticker, data in histories.items()}, axis=1).sort_index()
    ema200 = closes.ewm(span=200, adjust=False).mean()
    valid = closes.notna() & ema200.notna()
    return ((closes > ema200) & valid).sum(axis=1) / valid.sum(axis=1).replace(0, np.nan)


def _candidate_rows(histories: dict[str, pd.DataFrame], spy: pd.DataFrame, qqq: pd.DataFrame) -> list[dict]:
    breadth = _breadth(histories)
    spy_ema50, spy_ema200 = spy["Close"].ewm(span=50, adjust=False).mean(), spy["Close"].ewm(span=200, adjust=False).mean()
    qqq_ema200 = qqq["Close"].ewm(span=200, adjust=False).mean()
    rows: list[dict] = []
    for ticker, data in histories.items():
        for index in range(WARMUP_BARS, len(data) - MAX_HOLDING_DAYS - SELECTED["entry_wait"]):
            signal_date = data.index[index]
            if signal_date not in spy.index or signal_date not in qqq.index or signal_date not in breadth.index:
                continue
            history, spy_history = data.iloc[:index + 1], spy.loc[:signal_date]
            atr = safe_float(add_atr(history)["ATR"].iloc[-1])
            if not atr or atr <= 0:
                continue
            market = analyze_market_regime(spy_history, history)
            rows.append({
                "ticker": ticker, "sector": SYMBOLS[ticker], "index": index, "signal_date": str(signal_date.date()),
                "ema20": float(history["Close"].ewm(span=20, adjust=False).mean().iloc[-1]),
                "swing_low_20": float(history.tail(20)["Low"].min()), "atr": float(atr),
                "spy_close_ema200": bool(float(spy.loc[signal_date, "Close"]) > float(spy_ema200.loc[signal_date])),
                "spy_ema50_ema200": bool(float(spy_ema50.loc[signal_date]) > float(spy_ema200.loc[signal_date])),
                "spy_dual_ema": bool(float(spy.loc[signal_date, "Close"]) > float(spy_ema200.loc[signal_date]) and float(spy_ema50.loc[signal_date]) > float(spy_ema200.loc[signal_date])),
                "nasdaq_close_ema200": bool(float(qqq.loc[signal_date, "Close"]) > float(qqq_ema200.loc[signal_date])),
                "universe_breadth_60": bool(float(breadth.loc[signal_date]) >= .60),
                "existing_market_regime": bool(market["score"] >= 65),
            })
    rows.sort(key=lambda row: (row["signal_date"], row["ticker"]))
    split = int(len(rows) * .7)
    oos_keys = {(row["ticker"], row["index"]) for row in rows[split:]}
    for row in rows: row["out_of_sample"] = (row["ticker"], row["index"]) in oos_keys; row["walk_forward_period"] = "Calibration" if not row["out_of_sample"] else "Out of sample"
    return rows


def _run(filter_id: str, candidates: list[dict], histories: dict[str, pd.DataFrame], cost_multiplier: int) -> tuple[list[dict], list[dict], int]:
    trades: list[dict] = []; rejected: list[dict] = []; active: dict[str, int] = defaultdict(lambda: -1); eligible = 0
    for candidate in sorted(candidates, key=lambda row: (row["ticker"], row["index"])):
        shared = {key: value for key, value in candidate.items() if key != "index"}
        shared.update({"filter_id": filter_id, "filter_name": FILTERS[filter_id], "cost_multiplier": cost_multiplier})
        allowed = filter_id == "ungated" or candidate[filter_id]
        if not allowed:
            rejected.append({"record_type": "REJECTED", **shared, "reason": "Market regime filter disallowed long entry"}); continue
        eligible += 1
        if candidate["index"] + 1 <= active[candidate["ticker"]]:
            rejected.append({"record_type": "REJECTED", **shared, "reason": "Overlapping position for ticker"}); continue
        data = histories[candidate["ticker"]]
        entry_index = next((idx for idx in range(candidate["index"] + 1, candidate["index"] + 1 + SELECTED["entry_wait"]) if float(data.iloc[idx]["Low"]) <= candidate["ema20"] <= float(data.iloc[idx]["High"])), None)
        if entry_index is None:
            rejected.append({"record_type": "REJECTED", **shared, "reason": "Pullback limit was not traded within 3 candles"}); continue
        entry = entry_fill_price(candidate["ema20"], SLIPPAGE_BPS * cost_multiplier); stop = candidate["swing_low_20"] - SELECTED["stop_atr"] * candidate["atr"]; risk = entry - stop
        if risk <= 0 or risk / entry > MAX_RISK_PCT:
            rejected.append({"record_type": "REJECTED", **shared, "reason": "Position risk exceeds 5% of entry price"}); continue
        outcome = _simulate(data, entry_index, entry, stop, entry + SELECTED["target_1_r"] * risk, entry + SELECTED["target_2_r"] * risk, SELECTED["tp1_portion"], SLIPPAGE_BPS * cost_multiplier, TRANSACTION_COST_BPS * cost_multiplier)
        if outcome is None:
            rejected.append({"record_type": "REJECTED", **shared, "reason": "Invalid executable trade"}); continue
        active[candidate["ticker"]] = outcome["exit_index"]
        trades.append({"record_type": "TRADE", "trade_id": f"{filter_id}-{candidate['ticker']}-{candidate['signal_date']}", **shared, "entry_date": str(data.index[entry_index].date()), "entry_price": entry, "stop_loss": stop, "target_1": entry + SELECTED["target_1_r"] * risk, "target_2": entry + SELECTED["target_2_r"] * risk, "exit_date": str(data.index[outcome["exit_index"]].date()), **outcome})
    return trades, rejected, eligible


def _summary(trades: list[dict], rejected: list[dict], eligible: int) -> dict:
    full = _metrics(trades, len(rejected)); full["eligible_signals"] = eligible
    oos_trades, oos_rejected = [row for row in trades if row["out_of_sample"]], [row for row in rejected if row["out_of_sample"]]
    oos = _metrics(oos_trades, len(oos_rejected)); oos["eligible_signals"] = sum(row["out_of_sample"] for row in trades + rejected if row.get("reason") != "Market regime filter disallowed long entry")
    return {"overall": full, "out_of_sample": oos, "by_sector": _group(trades, rejected, "sector"), "by_walk_forward_period": _group(trades, rejected, "walk_forward_period"), "rejection_reasons": dict(sorted(Counter(row["reason"] for row in rejected).items()))}


def _baselines(histories: dict[str, pd.DataFrame], candidates: list[dict], ungated_oos: list[dict]) -> dict:
    start = pd.Timestamp(min(row["signal_date"] for row in candidates if row["out_of_sample"])); end = min(data.index[-1] for data in histories.values())
    buy_hold = []
    for ticker, data in histories.items():
        window = data.loc[start:end]
        if len(window) > 1: buy_hold.append((float(window["Close"].iloc[-1]) / float(window["Open"].iloc[0]) - 1) * 100)
    ema = []
    for ticker, data in histories.items():
        window = data.loc[start:end].copy(); fast = window["Close"].ewm(span=20, adjust=False).mean(); slow = window["Close"].ewm(span=50, adjust=False).mean()
        for index in range(1, len(window) - 30):
            if fast.iloc[index] > slow.iloc[index] and fast.iloc[index - 1] <= slow.iloc[index - 1]: ema.append((float(window["Close"].iloc[index + 30]) / float(window["Open"].iloc[index + 1]) - 1) * 100)
    rng = np.random.default_rng(RANDOM_SEED); random_returns = []
    for trade in ungated_oos:
        data = histories[trade["ticker"]]; index = int(rng.integers(WARMUP_BARS, len(data) - 31)); random_returns.append((float(data.iloc[index + 30]["Close"]) / float(data.iloc[index + 1]["Open"]) - 1) * 100)
    def simple(values):
        values = np.array(values, dtype=float); return {"observations": len(values), "average_return_pct": round(float(values.mean()), 4) if len(values) else 0, "win_rate": round(float((values > 0).mean() * 100), 2) if len(values) else 0}
    return {"buy_and_hold": simple(buy_hold), "ema20_ema50_crossover": simple(ema), "matched_random_entries": simple(random_returns)}


def run_audit(provider=None) -> dict:
    provider = provider or get_market_data_provider(); end = date.today() - timedelta(days=1); start = end - timedelta(days=5 * 365 + 15)
    histories = {ticker: _load_cached(ticker) for ticker in SYMBOLS}; spy = _load_cached("SPY")
    qqq, qqq_error = _history(provider, "QQQ", start, end)
    if qqq_error or qqq is None: return {"audit_status": "blocked", "reason": f"QQQ history unavailable: {qqq_error}"}
    candidates = _candidate_rows(histories, spy, qqq); results = {}; ledger = []; ungated_oos: list[dict] = []
    for filter_id in FILTERS:
        trades, rejected, eligible = _run(filter_id, candidates, histories, 1); double_trades, double_rejected, double_eligible = _run(filter_id, candidates, histories, 2)
        result = _summary(trades, rejected, eligible); result["double_cost"] = _summary(double_trades, double_rejected, double_eligible)["overall"]
        results[filter_id] = result; ledger.extend(trades + rejected)
        if filter_id == "ungated": ungated_oos = [row for row in trades if row["out_of_sample"]]
    approved = []
    for filter_id, result in results.items():
        oos, double, sectors, periods = result["out_of_sample"], result["double_cost"], result["by_sector"], result["by_walk_forward_period"]
        profits = [max(0, value["expectancy"]) * value["accepted_trades"] for value in sectors.values()]; sector_concentration = max(profits) / sum(profits) if sum(profits) else 1
        period_profits = [max(0, value["expectancy"]) * value["accepted_trades"] for value in periods.values()]; period_concentration = max(period_profits) / sum(period_profits) if sum(period_profits) else 1
        ci = oos["expectancy_95_ci"]
        if filter_id != "ungated" and oos["accepted_trades"] >= 100 and (double["profit_factor"] or 0) > 1 and ci and ci[0] >= 0 and sector_concentration <= .5 and period_concentration <= .7: approved.append(filter_id)
    return {"audit_status": "completed", "parameters": {"universe_size": len(histories), "dataset": "cached five-year daily OHLCV", "selected_pullback_settings": SELECTED, "signal_timing": "regime evaluated on signal-close information only", "out_of_sample": "chronological final 30% of raw signal dates", "costs": "slippage and transaction costs both doubled for stress test"}, "candidate_signals": len(candidates), "filters": results, "baselines": _baselines(histories, candidates, ungated_oos), "production_recommendation": {"approved_filters": [], "mechanically_passing_filters": approved, "decision": "No regime filter is approved for production; a separate locked validation is required after selecting a filter."}, "rows": ledger}


def write_artifacts(results: dict) -> None:
    OUTPUT.mkdir(exist_ok=True); (OUTPUT / "regime_gated_pullback_results.json").write_text(json.dumps({key: value for key, value in results.items() if key != "rows"}, indent=2)); rows = []
    for row in results.get("rows", []):
        shared = {key: value for key, value in row.items() if key != "exit_legs"}
        if row["record_type"] == "TRADE":
            for number, leg in enumerate(row["exit_legs"], 1): rows.append({**shared, "leg_number": number, **{f"leg_{key}": value for key, value in leg.items()}})
        else: rows.append(shared)
    with (OUTPUT / "regime_gated_pullback_trades.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted({key for row in rows for key in row}) if rows else ["ticker"], lineterminator="\n"); writer.writeheader(); writer.writerows(rows)


if __name__ == "__main__":
    result = run_audit(); write_artifacts(result); print(json.dumps({key: value for key, value in result.items() if key != "rows"}, indent=2))
