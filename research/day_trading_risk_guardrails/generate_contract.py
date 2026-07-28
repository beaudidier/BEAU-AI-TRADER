#!/usr/bin/env python3
"""Generate the research-only day-trading guardrail contract and test vectors."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "DAY_TRADING_RISK_GUARDRAILS.md"
OUT = Path(__file__).resolve().parent

MODES = {
    "BEGINNER": {
        "risk_per_trade_ppm": 2500,
        "risk_per_trade_cap_cents": 10000,
        "daily_loss_ppm": 10000,
        "weekly_loss_ppm": 25000,
        "drawdown_ppm": 50000,
        "consecutive_losses": 2,
        "position_count": 2,
        "total_open_risk_ppm": 5000,
        "daily_new_risk_ppm": 10000,
        "position_notional_ppm": 200000,
        "gross_exposure_ppm": 500000,
        "sector_exposure_ppm": 200000,
        "correlated_exposure_ppm": 250000,
        "unknown_sector_ppm": 0,
        "quote_age_decision_ms": 1000,
        "quote_age_submit_ms": 1500,
        "spread_abs_micros": 50000,
        "spread_ppm": 5000,
        "bid_ask_size_shares": 500,
        "bid_ask_size_cents": 500000,
        "dollar_volume_cents": 2_000_000_000,
        "price_cents": 500,
        "volatility_5m_ppm": 15000,
        "gap_ppm": 50000,
        "open_block_until_et": "09:45:00",
        "new_risk_cutoff_et": "15:30:00",
        "flatten_deadline_et": "15:50:00",
        "slippage_ppm": 1000,
        "latency_ms": 750,
        "shorts_allowed": False,
    },
    "ADVANCED": {
        "risk_per_trade_ppm": 5000,
        "risk_per_trade_cap_cents": 50000,
        "daily_loss_ppm": 20000,
        "weekly_loss_ppm": 40000,
        "drawdown_ppm": 80000,
        "consecutive_losses": 3,
        "position_count": 5,
        "total_open_risk_ppm": 15000,
        "daily_new_risk_ppm": 25000,
        "position_notional_ppm": 300000,
        "gross_exposure_ppm": 1_000_000,
        "sector_exposure_ppm": 350000,
        "correlated_exposure_ppm": 500000,
        "unknown_sector_ppm": 100000,
        "quote_age_decision_ms": 750,
        "quote_age_submit_ms": 1000,
        "spread_abs_micros": 100000,
        "spread_ppm": 7500,
        "bid_ask_size_shares": 200,
        "bid_ask_size_cents": 200000,
        "dollar_volume_cents": 1_000_000_000,
        "price_cents": 300,
        "volatility_5m_ppm": 25000,
        "gap_ppm": 80000,
        "open_block_until_et": "09:35:00",
        "new_risk_cutoff_et": "15:40:00",
        "flatten_deadline_et": "15:55:00",
        "slippage_ppm": 2000,
        "latency_ms": 500,
        "shorts_allowed": True,
    },
    "PAPER": {
        "risk_per_trade_ppm": 2500,
        "risk_per_trade_cap_cents": 25000,
        "daily_loss_ppm": 15000,
        "weekly_loss_ppm": 30000,
        "drawdown_ppm": 60000,
        "consecutive_losses": 3,
        "position_count": 3,
        "total_open_risk_ppm": 7500,
        "daily_new_risk_ppm": 15000,
        "position_notional_ppm": 250000,
        "gross_exposure_ppm": 750000,
        "sector_exposure_ppm": 250000,
        "correlated_exposure_ppm": 350000,
        "unknown_sector_ppm": 0,
        "quote_age_decision_ms": 1000,
        "quote_age_submit_ms": 1500,
        "spread_abs_micros": 50000,
        "spread_ppm": 5000,
        "bid_ask_size_shares": 500,
        "bid_ask_size_cents": 500000,
        "dollar_volume_cents": 1_500_000_000,
        "price_cents": 500,
        "volatility_5m_ppm": 20000,
        "gap_ppm": 60000,
        "open_block_until_et": "09:40:00",
        "new_risk_cutoff_et": "15:35:00",
        "flatten_deadline_et": "15:50:00",
        "slippage_ppm": 1500,
        "latency_ms": 750,
        "shorts_allowed": False,
    },
    "FUTURE_LIVE": {
        "risk_per_trade_ppm": 2500,
        "risk_per_trade_cap_cents": 25000,
        "daily_loss_ppm": 10000,
        "weekly_loss_ppm": 25000,
        "drawdown_ppm": 50000,
        "consecutive_losses": 2,
        "position_count": 3,
        "total_open_risk_ppm": 5000,
        "daily_new_risk_ppm": 10000,
        "position_notional_ppm": 200000,
        "gross_exposure_ppm": 500000,
        "sector_exposure_ppm": 200000,
        "correlated_exposure_ppm": 250000,
        "unknown_sector_ppm": 0,
        "quote_age_decision_ms": 500,
        "quote_age_submit_ms": 750,
        "spread_abs_micros": 50000,
        "spread_ppm": 3500,
        "bid_ask_size_shares": 1000,
        "bid_ask_size_cents": 1_000_000,
        "dollar_volume_cents": 2_500_000_000,
        "price_cents": 500,
        "volatility_5m_ppm": 15000,
        "gap_ppm": 50000,
        "open_block_until_et": "09:45:00",
        "new_risk_cutoff_et": "15:30:00",
        "flatten_deadline_et": "15:45:00",
        "slippage_ppm": 1000,
        "latency_ms": 300,
        "shorts_allowed": False,
    },
}

CATEGORIES = {
    "account_risk": [
        "RISK_PER_TRADE_MAX", "DAILY_LOSS_MAX", "WEEKLY_LOSS_MAX",
        "ACCOUNT_DRAWDOWN_MAX", "CONSECUTIVE_LOSSES_MAX",
        "TOTAL_OPEN_RISK_MAX", "DAILY_NEW_RISK_MAX", "ACCOUNT_LOCKED",
    ],
    "position_risk": [
        "POSITION_COUNT_MAX", "POSITION_NOTIONAL_MAX", "GROSS_EXPOSURE_MAX",
        "SECTOR_EXPOSURE_MAX", "CORRELATED_EXPOSURE_MAX", "SECTOR_UNKNOWN",
        "AVERAGING_DOWN_BLOCKED", "MARTINGALE_BLOCKED", "FLATTEN_REQUIRED",
    ],
    "market_data": [
        "QUOTE_STALE", "QUOTE_INVALID", "DATA_FEED_UNHEALTHY", "SPREAD_MAX",
        "DISPLAYED_SIZE_MIN", "DOLLAR_VOLUME_MIN", "DOLLAR_VOLUME_HISTORY",
        "PRICE_MIN", "INSTRUMENT_INELIGIBLE", "PARTIAL_IEX_LIVE_BLOCK",
        "DATA_ENTITLEMENT_UNVERIFIED", "VOLATILITY_MAX", "ABNORMAL_GAP",
        "CLOCK_UNSYNCHRONIZED",
    ],
    "market_event": [
        "TRADING_HALT", "LULD_PAUSE", "SSR_SHORT_BLOCK", "SHORTS_DISABLED",
        "SESSION_NOT_REGULAR", "AUCTION_RESTRICTED", "FIRST_MINUTE_BLOCK",
        "FINAL_MINUTE_BLOCK", "OPENING_WINDOW", "NEW_RISK_CUTOFF",
        "EARNINGS_BLACKOUT", "BREAKING_NEWS", "NEWS_FEED_UNHEALTHY",
        "ECONOMIC_EVENT", "FED_EVENT", "EVENT_DATA_UNHEALTHY",
    ],
    "order_safety": [
        "ORDER_TYPE_UNSUPPORTED", "SLIPPAGE_MAX", "LATENCY_MAX",
        "DUPLICATE_ORDER", "STALE_STATE", "CONCURRENT_STATE_CONFLICT",
        "ORDER_STATE_UNKNOWN", "PARTIAL_FILL_RISK", "BROKER_REJECTION",
        "BROKER_DISCONNECTED", "PROTECTIVE_STOP_INVALID",
        "RISK_STATE_UNAVAILABLE", "AUDIT_WRITE_FAILED", "KILL_SWITCH_ACTIVE",
        "LIVE_TRADING_DISABLED",
    ],
}

THRESHOLDS = {
    "RISK_PER_TRADE_MAX": ("risk_per_trade_ppm", "max", "ppm"),
    "DAILY_LOSS_MAX": ("daily_loss_ppm", "tripwire", "ppm"),
    "WEEKLY_LOSS_MAX": ("weekly_loss_ppm", "tripwire", "ppm"),
    "ACCOUNT_DRAWDOWN_MAX": ("drawdown_ppm", "tripwire", "ppm"),
    "CONSECUTIVE_LOSSES_MAX": ("consecutive_losses", "tripwire", "count"),
    "TOTAL_OPEN_RISK_MAX": ("total_open_risk_ppm", "max", "ppm"),
    "DAILY_NEW_RISK_MAX": ("daily_new_risk_ppm", "max", "ppm"),
    "POSITION_COUNT_MAX": ("position_count", "max", "count"),
    "POSITION_NOTIONAL_MAX": ("position_notional_ppm", "max", "ppm"),
    "GROSS_EXPOSURE_MAX": ("gross_exposure_ppm", "max", "ppm"),
    "SECTOR_EXPOSURE_MAX": ("sector_exposure_ppm", "max", "ppm"),
    "CORRELATED_EXPOSURE_MAX": ("correlated_exposure_ppm", "max", "ppm"),
    "QUOTE_STALE": ("quote_age_decision_ms", "max", "ms"),
    "DOLLAR_VOLUME_MIN": ("dollar_volume_cents", "min", "cents"),
    "PRICE_MIN": ("price_cents", "min", "cents"),
    "VOLATILITY_MAX": ("volatility_5m_ppm", "tripwire", "ppm"),
    "ABNORMAL_GAP": ("gap_ppm", "tripwire", "ppm"),
    "SLIPPAGE_MAX": ("slippage_ppm", "max", "ppm"),
    "LATENCY_MAX": ("latency_ms", "max", "ms"),
}

UNRESOLVED_FUTURE_LIVE = {
    "SSR_SHORT_BLOCK": ["broker", "short_sale", "legal"],
    "SHORTS_DISABLED": ["broker", "short_sale", "legal"],
    "PARTIAL_IEX_LIVE_BLOCK": ["data_provider", "licensing", "entitlement"],
    "DATA_ENTITLEMENT_UNVERIFIED": ["data_provider", "licensing", "entitlement"],
    "LIVE_TRADING_DISABLED": [
        "broker", "legal", "licensing", "entitlement", "compliance",
        "jurisdiction", "PDT", "suitability", "user_disclosure",
    ],
}

STATEFUL_SCENARIOS = [
    ("STATE_DAILY_LOSS", ["fill_loss", "mark_to_market"], "DAILY_LOSS_MAX"),
    ("STATE_WEEKLY_LOSS", ["begin_rolling_window", "session_losses_x5"], "WEEKLY_LOSS_MAX"),
    ("STATE_DRAWDOWN", ["new_high_water", "equity_decline"], "ACCOUNT_DRAWDOWN_MAX"),
    ("STATE_OPEN_RISK", ["reserve_order", "partial_fill"], "TOTAL_OPEN_RISK_MAX"),
    ("STATE_NEW_RISK", ["accept_order", "cancel_unfilled"], "DAILY_NEW_RISK_MAX"),
    ("STATE_PARTIAL_FILL", ["partial_fill", "protect_timeout"], "PARTIAL_FILL_RISK"),
    ("STATE_STALE", ["decision", "state_version_change"], "STALE_STATE"),
    ("STATE_RECONNECT", ["broker_disconnect", "reconnect_without_reconcile"], "BROKER_DISCONNECTED"),
    ("STATE_RESTART", ["restart", "unreconciled_state"], "RISK_STATE_UNAVAILABLE"),
    ("STATE_KILL_LOCK", ["kill_switch", "restart"], "KILL_SWITCH_ACTIVE"),
    ("STATE_MULTI_WORKER", ["worker_a_fence", "worker_b_stale_fence"], "CONCURRENT_STATE_CONFLICT"),
]


def parse_markdown() -> tuple[dict[str, str], dict[str, str]]:
    text = DOC.read_text(encoding="utf-8")
    messages: dict[str, str] = {}
    for code, message in re.findall(
        r"^\| `([A-Z][A-Z0-9_]+)` \| “(.+?)” \|$", text, re.MULTILINE
    ):
        if code in messages:
            raise ValueError(f"duplicate canonical reason code: {code}")
        messages[code] = message

    recovery: dict[str, str] = {}
    in_recovery = False
    for line in text.splitlines():
        if line.startswith("### 11.1 "):
            in_recovery = True
        elif in_recovery and line.startswith("## 12."):
            break
        elif in_recovery and line.startswith("| `"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) != 2:
                continue
            codes = re.findall(r"`([A-Z][A-Z0-9_]+)`", cells[0])
            for code in codes:
                if code in recovery:
                    raise ValueError(f"duplicate recovery action: {code}")
                recovery[code] = cells[1]
    return messages, recovery


def build_contract() -> dict:
    messages, recovery = parse_markdown()
    category_by_code = {
        code: category for category, codes in CATEGORIES.items() for code in codes
    }
    if set(messages) != set(category_by_code):
        raise ValueError(
            f"category mismatch missing={sorted(set(messages)-set(category_by_code))} "
            f"unused={sorted(set(category_by_code)-set(messages))}"
        )
    if set(messages) != set(recovery):
        raise ValueError(
            f"recovery mismatch missing={sorted(set(messages)-set(recovery))} "
            f"unused={sorted(set(recovery)-set(messages))}"
        )

    ordered_codes = list(messages)
    rules = []
    for priority, code in enumerate(ordered_codes, start=1):
        threshold = THRESHOLDS.get(code)
        rules.append(
            {
                "rule_id": f"DT.{code}",
                "reason_code": code,
                "category": category_by_code[code],
                "priority": priority,
                "condition": (
                    {
                        "kind": "threshold",
                        "mode_limit_key": threshold[0],
                        "boundary": threshold[1],
                        "unit": threshold[2],
                        "max_allows_equality": threshold[1] == "max",
                        "min_allows_equality": threshold[1] == "min",
                        "tripwire_blocks_equality": threshold[1] == "tripwire",
                    }
                    if threshold
                    else {"kind": "explicit_boolean_violation", "trigger_value": True}
                ),
                "missing_or_conflicting_input": "BLOCK_FAIL_CLOSED",
                "user_message": messages[code],
                "recovery_action": recovery[code],
                "override_allowed": False,
                "override_authority": "NONE",
                "future_live_status": (
                    "UNRESOLVED_FAIL_CLOSED"
                    if code in UNRESOLVED_FUTURE_LIVE
                    else "DEFINED"
                ),
                "unresolved_dependencies": UNRESOLVED_FUTURE_LIVE.get(code, []),
                "source": {
                    "document": "docs/DAY_TRADING_RISK_GUARDRAILS.md",
                    "reason_section": "11",
                    "recovery_section": "11.1",
                },
            }
        )

    return {
        "contract_id": "day-trading-risk-guardrails",
        "contract_version": 1,
        "status": "RESEARCH_PAPER_ONLY",
        "live_execution": "HARD_DISABLED",
        "legal_or_regulatory_compliance_claim": False,
        "numeric_representation": {
            "money": "integer cents unless field suffix is _micros",
            "rates": "integer parts per million (ppm)",
            "time": "integer milliseconds or America/New_York HH:MM:SS",
            "floating_point_prohibited": True,
        },
        "evaluation": {
            "fail_closed": True,
            "unknown_missing_conflicting": "RISK_STATE_UNAVAILABLE",
            "primary_reason": "lowest integer priority among all active reasons",
            "secondary_reasons": "remaining active reasons sorted by priority then reason_code",
            "input_order_independent": True,
            "rule_order_independent": True,
        },
        "modes": MODES,
        "rules": rules,
        "stateful_requirements": {
            "durable_before_ack": True,
            "single_writer_per_account": True,
            "serializable_transactions": True,
            "fencing_token_required": True,
            "restart_state": [
                "daily_loss", "weekly_loss", "drawdown", "high_water_mark",
                "total_open_risk", "daily_new_risk", "partial_fills",
                "idempotency", "stale_state", "lockout", "kill_switch",
            ],
        },
    }


def triggers(boundary: str, observed: int, limit: int) -> bool:
    if boundary == "max":
        return observed > limit
    if boundary == "min":
        return observed < limit
    if boundary == "tripwire":
        return observed >= limit
    raise ValueError(f"unknown boundary: {boundary}")


def build_vectors(contract: dict) -> dict:
    vectors = []
    for rule in contract["rules"]:
        code = rule["reason_code"]
        base = {
            "rule_id": rule["rule_id"],
            "reason_code": code,
            "mode": "PAPER",
        }
        condition = rule["condition"]
        if condition["kind"] == "threshold":
            limit = MODES["PAPER"][condition["mode_limit_key"]]
            boundary = condition["boundary"]
            cases = {
                "just_below": limit - 1,
                "equal": limit,
                "just_above": limit + 1,
            }
            for label, observed in cases.items():
                blocked = triggers(boundary, observed, limit)
                vectors.append(
                    {
                        **base,
                        "testvector_id": f"TV.{code}.{label.upper()}",
                        "kind": "boundary",
                        "input": {"observed": observed, "limit": limit},
                        "expected": {
                            "decision": "BLOCK" if blocked else "ALLOW",
                            "primary_reason": code if blocked else None,
                        },
                    }
                )
        else:
            for label, active in (("NEGATIVE", False), ("POSITIVE", True)):
                vectors.append(
                    {
                        **base,
                        "testvector_id": f"TV.{code}.{label}",
                        "kind": "boolean",
                        "input": {"violation": active},
                        "expected": {
                            "decision": "BLOCK" if active else "ALLOW",
                            "primary_reason": code if active else None,
                        },
                    }
                )

        vectors.append(
            {
                **base,
                "testvector_id": f"TV.{code}.MISSING",
                "kind": "fail_closed",
                "input": {"required_input": None},
                "expected": {
                    "decision": "BLOCK",
                    "primary_reason": "RISK_STATE_UNAVAILABLE",
                },
            }
        )

    priorities = {rule["reason_code"]: rule["priority"] for rule in contract["rules"]}
    combinations = [
        ["SPREAD_MAX", "QUOTE_STALE"],
        ["EARNINGS_BLACKOUT", "DAILY_LOSS_MAX", "SPREAD_MAX"],
        ["DUPLICATE_ORDER", "TRADING_HALT", "LATENCY_MAX"],
        ["KILL_SWITCH_ACTIVE", "ACCOUNT_LOCKED", "RISK_STATE_UNAVAILABLE"],
    ]
    for index, active in enumerate(combinations, start=1):
        expected = sorted(active, key=lambda code: (priorities[code], code))
        vectors.append(
            {
                "testvector_id": f"TV.MULTI.{index:02d}",
                "kind": "multi_block",
                "mode": "PAPER",
                "active_reasons": list(reversed(active)),
                "expected": {
                    "decision": "BLOCK",
                    "primary_reason": expected[0],
                    "all_reasons": expected,
                },
            }
        )

    for scenario_id, steps, reason in STATEFUL_SCENARIOS:
        vectors.append(
            {
                "testvector_id": f"TV.{scenario_id}",
                "kind": "stateful",
                "mode": "PAPER",
                "steps": steps,
                "expected": {
                    "decision": "BLOCK",
                    "primary_reason": reason,
                    "state_persists_restart": scenario_id
                    in {"STATE_RESTART", "STATE_KILL_LOCK"},
                },
            }
        )

    vectors.append(
        {
            "testvector_id": "TV.FUTURE_LIVE.UNRESOLVED",
            "kind": "future_live_fail_closed",
            "mode": "FUTURE_LIVE",
            "unresolved_dependencies": sorted(
                {
                    dependency
                    for values in UNRESOLVED_FUTURE_LIVE.values()
                    for dependency in values
                }
            ),
            "expected": {
                "decision": "BLOCK",
                "primary_reason": "LIVE_TRADING_DISABLED",
            },
        }
    )
    return {"contract_id": contract["contract_id"], "vectors": vectors}


def canonical_json(data: dict) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> None:
    contract = build_contract()
    vectors = build_vectors(contract)
    contract_text = canonical_json(contract)
    vector_text = canonical_json(vectors)
    (OUT / "policy.json").write_text(contract_text, encoding="utf-8")
    (OUT / "testvectors.json").write_text(vector_text, encoding="utf-8")
    manifest = {
        "contract_sha256": hashlib.sha256(contract_text.encode()).hexdigest(),
        "testvectors_sha256": hashlib.sha256(vector_text.encode()).hexdigest(),
        "generator": "research/day_trading_risk_guardrails/generate_contract.py",
    }
    (OUT / "manifest.json").write_text(canonical_json(manifest), encoding="utf-8")


if __name__ == "__main__":
    main()
