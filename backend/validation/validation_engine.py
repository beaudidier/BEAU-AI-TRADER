"""Deterministic forward validation for recorded recommendations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pandas as pd

WINDOWS = (1, 3, 7, 14, 30)


class RecommendationValidationStore:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []
        self._keys: set[str] = set()

    def record(self, ticker: str, confidence: float, verdict: str, entry: float, stop: float, target: float, market_regime: str, timestamp: datetime | None = None) -> dict[str, Any]:
        created = timestamp or datetime.now(timezone.utc)
        key = f"{ticker.upper()}:{created.date().isoformat()}:{verdict}"
        if key in self._keys:
            return next(item for item in self.records if item["key"] == key)
        record = {"id": str(uuid4()), "key": key, "ticker": ticker.upper(), "confidence": round(float(confidence), 2), "verdict": verdict, "timestamp": created.isoformat(), "entry": round(float(entry), 2), "stop": round(float(stop), 2), "target": round(float(target), 2), "market_regime": market_regime, "evaluations": {}}
        self._keys.add(key); self.records.append(record)
        return record

    def evaluate(self, record: dict[str, Any], history: pd.DataFrame) -> dict[str, Any]:
        start = pd.Timestamp(record["timestamp"]).tz_localize(None)
        future = history[history.index > start]
        if future.empty:
            return record
        entry, stop, target = (float(record[key]) for key in ("entry", "stop", "target"))
        risk = max(entry - stop, 0.000001)
        for days in WINDOWS:
            if str(days) in record["evaluations"]:
                continue
            window = future[future.index <= start + timedelta(days=days)]
            if window.empty or pd.Timestamp(window.index[-1]) < start + timedelta(days=days):
                continue
            high, low = float(window["High"].max()), float(window["Low"].min())
            target_2 = entry + (target - entry) * 2
            record["evaluations"][str(days)] = {"days": days, "tp1_hit": high >= target, "tp2_hit": high >= target_2, "stop_hit": low <= stop, "maximum_favorable_excursion": round((high - entry) / risk, 2), "maximum_adverse_excursion": round((low - entry) / risk, 2), "evaluated_at": datetime.now(timezone.utc).isoformat()}
        return record

    def refresh(self, get_history) -> None:
        """Evaluate every due window when validation metrics are requested."""

        for record in self.records:
            try:
                history = get_history(record["ticker"], period="6mo", interval="1d")
                if history is not None and not history.empty:
                    self.evaluate(record, history)
            except Exception:
                continue

    def dashboard(self) -> dict[str, Any]:
        outcomes = [(record, evaluation) for record in self.records for evaluation in record["evaluations"].values()]
        def accuracy(items: list[tuple[dict[str, Any], dict[str, Any]]]) -> float:
            return round(sum(1 for _, item in items if item["tp1_hit"] and not item["stop_hit"]) / len(items) * 100, 1) if items else 0.0
        def ev(items: list[tuple[dict[str, Any], dict[str, Any]]]) -> float:
            return round(sum(item["maximum_favorable_excursion"] + item["maximum_adverse_excursion"] for _, item in items) / len(items), 2) if items else 0.0
        by_verdict = {label: accuracy([item for item in outcomes if item[0]["verdict"] == label]) for label in ("BUY", "WATCH", "STRONG BUY")}
        confidence = {"90-100": accuracy([item for item in outcomes if item[0]["confidence"] >= 90]), "75-89": accuracy([item for item in outcomes if 75 <= item[0]["confidence"] < 90]), "60-74": accuracy([item for item in outcomes if 60 <= item[0]["confidence"] < 75])}
        regimes = {regime: accuracy([item for item in outcomes if item[0]["market_regime"] == regime]) for regime in sorted({item[0]["market_regime"] for item in outcomes})}
        best = max(regimes, key=regimes.get) if regimes else None; worst = min(regimes, key=regimes.get) if regimes else None
        return {"overall_accuracy": accuracy(outcomes), "buy_accuracy": by_verdict["BUY"], "watch_accuracy": by_verdict["WATCH"], "strong_buy_accuracy": by_verdict["STRONG BUY"], "confidence_accuracy": confidence, "best_market_regime": {"regime": best, "accuracy": regimes.get(best, 0)}, "worst_market_regime": {"regime": worst, "accuracy": regimes.get(worst, 0)}, "expected_value": ev(outcomes), "tracked_recommendations": len(self.records), "evaluated_observations": len(outcomes)}


validation_store = RecommendationValidationStore()
