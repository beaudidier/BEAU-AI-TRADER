"""Deterministic, fixture-only news/event risk policy evaluator.

This module deliberately has no network, database, provider, broker, order,
strategy, portfolio, or UI integration.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
POLICY_PATH = ROOT / "policy.json"
SCHEMA_PATH = ROOT / "policy.schema.json"
VECTORS_PATH = ROOT / "test_vectors.json"
MANIFEST_PATH = ROOT / "artifact_manifest.json"

VALID_SEVERITIES = ("S0", "S1", "S2", "S3", "S4")
VALID_ACTIONS = (
    "informational",
    "ignore",
    "warning",
    "reduce_risk",
    "trade_block",
    "paper_only",
    "emergency_halt",
)
REQUIRED_RULE_FIELDS = {
    "rule_id",
    "document_section",
    "reason_code",
    "severity",
    "action",
    "priority",
    "required_inputs",
    "freshness_limit_seconds",
    "recovery_condition",
    "audit_payload",
    "condition",
}
REQUIRED_POLICY_FIELDS = {
    "contract_version",
    "status",
    "document",
    "determinism",
    "event_categories",
    "trust_levels",
    "severity_priority",
    "action_priority",
    "required_audit_fields",
    "unresolved_dependencies",
    "rules",
}
MINIMUM_RULE_AUDIT_FIELDS = {
    "source",
    "source_trust",
    "event_type",
    "published_at",
    "first_seen_at",
    "ingested_at",
    "severity",
    "action",
    "affected_tickers",
    "rule_id",
    "reason_code",
    "rule_version",
    "user_explanation",
    "expiry",
}
CRITICAL_EVENT_FIELDS = {
    "event_id",
    "event_type",
    "source_trust",
    "published_at",
    "first_seen_at",
    "ingested_at",
    "timezone",
    "mapping_status",
    "payload_state",
}
VALID_TRUST_LEVELS = {"T1", "T2", "T3", "T4", "T5", "T6"}
SCHEDULED_EVENT_TYPES = {
    "earnings_release",
    "earnings_call",
    "fed_decision",
    "cpi",
    "ppi",
    "jobs_report",
    "gdp",
    "treasury_event",
}


class ContractError(ValueError):
    """Raised when policy or fixture validation fails."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ContractError(f"{field}: missing timestamp")
    if not value.endswith("Z"):
        raise ContractError(f"{field}: UTC Z suffix required")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ContractError(f"{field}: invalid timestamp") from exc
    if parsed.tzinfo != timezone.utc:
        raise ContractError(f"{field}: UTC required")
    if not 2000 <= parsed.year <= 2100:
        raise ContractError(f"{field}: timestamp outside supported research range")
    return parsed


def validate_policy(policy: dict[str, Any], schema: dict[str, Any] | None = None) -> None:
    """Validate all contract invariants without external dependencies."""
    if not isinstance(policy, dict):
        raise ContractError("policy must be an object")
    if set(policy) != REQUIRED_POLICY_FIELDS:
        raise ContractError(
            f"policy fields mismatch missing={sorted(REQUIRED_POLICY_FIELDS - set(policy))} "
            f"extra={sorted(set(policy) - REQUIRED_POLICY_FIELDS)}"
        )
    if policy.get("contract_version") != "1.0.0":
        raise ContractError("unsupported contract_version")
    if policy.get("status") != "research_only":
        raise ContractError("status must be research_only")
    if policy.get("document") != "docs/NEWS_EVENT_RISK_ENGINE.md":
        raise ContractError("unexpected source document")
    determinism = policy.get("determinism")
    if not isinstance(determinism, dict):
        raise ContractError("determinism is required")
    expected_determinism = {
        "timezone": "UTC",
        "window_start_inclusive": True,
        "window_end_inclusive": True,
        "unknown_critical_input": "fail_closed",
    }
    if determinism != expected_determinism:
        raise ContractError("determinism settings are incomplete or conflicting")
    if policy.get("severity_priority") != ["S4", "S3", "S2", "S1", "S0"]:
        raise ContractError("severity priority must be S4 through S0")
    if policy.get("action_priority") != [
        "emergency_halt",
        "paper_only",
        "trade_block",
        "reduce_risk",
        "warning",
        "ignore",
        "informational",
    ]:
        raise ContractError("action priority is invalid")
    categories = policy.get("event_categories")
    if not isinstance(categories, list) or len(categories) < 21 or len(categories) != len(set(categories)):
        raise ContractError("event categories must be unique and complete")
    audit_fields = policy.get("required_audit_fields")
    if not isinstance(audit_fields, list) or len(audit_fields) < 15 or len(audit_fields) != len(set(audit_fields)):
        raise ContractError("required audit fields must be unique and complete")
    unresolved = policy.get("unresolved_dependencies")
    if not isinstance(unresolved, list) or len(unresolved) < 7 or len(unresolved) != len(set(unresolved)):
        raise ContractError("unresolved dependencies must be explicit and unique")

    rules = policy.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ContractError("rules must be a non-empty array")
    rule_ids: set[str] = set()
    reason_codes: set[str] = set()
    priorities: set[int] = set()
    condition_outputs: dict[str, tuple[str, str, str]] = {}
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ContractError(f"rule[{index}] must be an object")
        missing = REQUIRED_RULE_FIELDS - set(rule)
        extra = set(rule) - REQUIRED_RULE_FIELDS
        if missing or extra:
            raise ContractError(f"rule[{index}] missing={sorted(missing)} extra={sorted(extra)}")
        rule_id = rule["rule_id"]
        reason_code = rule["reason_code"]
        if not isinstance(rule_id, str) or not rule_id.startswith("NER-"):
            raise ContractError(f"rule[{index}] invalid rule_id")
        if not isinstance(reason_code, str) or not reason_code.startswith("NER_"):
            raise ContractError(f"rule[{index}] invalid reason_code")
        if rule_id in rule_ids:
            raise ContractError(f"duplicate rule_id: {rule_id}")
        if reason_code in reason_codes:
            raise ContractError(f"duplicate reason_code: {reason_code}")
        rule_ids.add(rule_id)
        reason_codes.add(reason_code)
        if rule["severity"] not in VALID_SEVERITIES:
            raise ContractError(f"{rule_id}: invalid severity")
        if rule["action"] not in VALID_ACTIONS:
            raise ContractError(f"{rule_id}: invalid action")
        priority = rule["priority"]
        if not isinstance(priority, int) or priority < 1 or priority in priorities:
            raise ContractError(f"{rule_id}: invalid or duplicate priority")
        priorities.add(priority)
        if not isinstance(rule["required_inputs"], list) or not rule["required_inputs"]:
            raise ContractError(f"{rule_id}: required_inputs missing")
        freshness = rule["freshness_limit_seconds"]
        if freshness is not None and (not isinstance(freshness, int) or freshness < 0):
            raise ContractError(f"{rule_id}: invalid freshness limit")
        if not isinstance(rule["recovery_condition"], str) or not rule["recovery_condition"]:
            raise ContractError(f"{rule_id}: recovery condition missing")
        if not isinstance(rule["audit_payload"], list) or not set(rule["audit_payload"]).issubset(audit_fields):
            raise ContractError(f"{rule_id}: invalid audit payload")
        if not MINIMUM_RULE_AUDIT_FIELDS.issubset(rule["audit_payload"]):
            raise ContractError(f"{rule_id}: required audit payload field missing")
        condition = rule["condition"]
        if not isinstance(condition, dict) or condition.get("kind") not in CONDITION_KINDS:
            raise ContractError(f"{rule_id}: undefined condition")
        _validate_condition(rule_id, condition)
        condition_key = canonical_json(condition)
        output = (rule["severity"], rule["action"], rule["recovery_condition"])
        previous = condition_outputs.get(condition_key)
        if previous is not None and previous != output:
            raise ContractError(f"{rule_id}: conflicting output/recovery for identical condition")
        condition_outputs[condition_key] = output
    if priorities != set(range(1, len(rules) + 1)):
        raise ContractError("rule priorities must be contiguous and unique")
    safety_invariants = {
        "NER-001": ("S3", "trade_block", "critical_invalid"),
        "NER-002": ("S4", "paper_only", "unresolved_live"),
        "NER-003": ("S4", "emergency_halt", "field_equals"),
        "NER-004": ("S3", "trade_block", "social_prohibited"),
        "NER-005": ("S3", "trade_block", "social_prohibited"),
        "NER-006": ("S3", "trade_block", "social_prohibited"),
    }
    indexed = {item["rule_id"]: item for item in rules}
    for rule_id, invariant in safety_invariants.items():
        item = indexed.get(rule_id)
        actual = None if item is None else (
            item["severity"], item["action"], item["condition"]["kind"]
        )
        if actual != invariant:
            raise ContractError(f"{rule_id}: mandatory safety invariant changed")
    if schema is not None:
        if schema.get("$id") != "urn:beau-ai-trader:news-event-risk-policy:v1":
            raise ContractError("schema identity mismatch")
        if set(schema.get("required", [])) - set(policy):
            raise ContractError("policy is missing a schema-required top-level field")


def validate_vector(vector: dict[str, Any]) -> None:
    required = {"vector_id", "rule_ids", "decision_at", "events", "expected"}
    if not isinstance(vector, dict) or set(vector) != required:
        raise ContractError("test vector fields are invalid")
    if not isinstance(vector["vector_id"], str) or not vector["vector_id"].startswith("TV-"):
        raise ContractError("invalid vector_id")
    if not isinstance(vector["rule_ids"], list) or not vector["rule_ids"]:
        raise ContractError("vector must trace to at least one rule")
    parse_timestamp(vector["decision_at"], "decision_at")
    if not isinstance(vector["events"], list):
        raise ContractError("events must be an array")
    if not vector["events"]:
        raise ContractError("events must not be empty")
    expected = vector["expected"]
    if not isinstance(expected, dict) or set(expected) != {
        "severity",
        "action",
        "reason_codes",
        "direction_effect",
        "confidence_delta_max",
        "size_multiplier_max",
    }:
        raise ContractError("expected result fields are invalid")
    if expected["severity"] not in VALID_SEVERITIES or expected["action"] not in VALID_ACTIONS:
        raise ContractError("expected severity/action is invalid")
    if not isinstance(expected["reason_codes"], list):
        raise ContractError("expected reason_codes must be an array")
    if expected["direction_effect"] != "none":
        raise ContractError("direction effect must remain none")
    if not isinstance(expected["confidence_delta_max"], (int, float)) or expected["confidence_delta_max"] > 0:
        raise ContractError("confidence_delta_max cannot be positive")
    multiplier = expected["size_multiplier_max"]
    if not isinstance(multiplier, (int, float)) or isinstance(multiplier, bool) or not 0 <= multiplier <= 1:
        raise ContractError("size_multiplier_max must be within [0,1]")


def _validate_condition(rule_id: str, condition: dict[str, Any]) -> None:
    kind = condition["kind"]
    expected_keys: dict[str, set[str]] = {
        "critical_invalid": {"kind"},
        "unresolved_live": {"kind"},
        "field_equals": {"kind", "field", "value"},
        "field_in": {"kind", "field", "values"},
        "all_equals": {"kind", "fields"},
        "window": {"kind", "event_types", "start_seconds", "end_seconds"},
        "freshness": {"kind", "event_types", "operator", "seconds"},
        "social_prohibited": {"kind", "field"},
        "social_freshness": {
            "kind", "source_trust", "verification_state", "operator", "seconds"
        },
    }
    if set(condition) != expected_keys[kind]:
        raise ContractError(f"{rule_id}: malformed {kind} condition")
    if kind in {"field_equals", "field_in", "social_prohibited"}:
        if not isinstance(condition["field"], str) or not condition["field"]:
            raise ContractError(f"{rule_id}: invalid condition field")
    if kind == "field_in" and (
        not isinstance(condition["values"], list) or not condition["values"]
    ):
        raise ContractError(f"{rule_id}: field_in values must not be empty")
    if kind == "all_equals" and (
        not isinstance(condition["fields"], dict) or not condition["fields"]
    ):
        raise ContractError(f"{rule_id}: all_equals fields must not be empty")
    if kind in {"window", "freshness"} and (
        not isinstance(condition["event_types"], list) or not condition["event_types"]
    ):
        raise ContractError(f"{rule_id}: event_types must not be empty")
    if kind == "window":
        start = condition["start_seconds"]
        end = condition["end_seconds"]
        if (
            not isinstance(start, int) or isinstance(start, bool)
            or not isinstance(end, int) or isinstance(end, bool)
            or start > end
            or abs(start) > 31_536_000
            or abs(end) > 31_536_000
        ):
            raise ContractError(f"{rule_id}: invalid or conflicting window bounds")
    if kind in {"freshness", "social_freshness"}:
        seconds = condition["seconds"]
        if (
            condition["operator"] not in {"lte", "gt"}
            or not isinstance(seconds, int)
            or isinstance(seconds, bool)
            or not 0 <= seconds <= 31_536_000
        ):
            raise ContractError(f"{rule_id}: invalid freshness condition")


def _seconds_from_event(event: dict[str, Any], decision_at: datetime) -> int:
    event_at = parse_timestamp(event.get("event_at"), "event_at")
    return int((decision_at - event_at).total_seconds())


def _critical_invalid(event: dict[str, Any], decision_at: datetime | None = None) -> bool:
    if not isinstance(event, dict) or CRITICAL_EVENT_FIELDS - set(event):
        return True
    if event.get("timezone") != "UTC":
        return True
    if event.get("source_trust") not in VALID_TRUST_LEVELS:
        return True
    if event.get("mapping_status") not in {"mapped", "not_applicable"}:
        return True
    if event.get("payload_state") != "valid":
        return True
    try:
        published = parse_timestamp(event.get("published_at"), "published_at")
        first_seen = parse_timestamp(event.get("first_seen_at"), "first_seen_at")
        ingested = parse_timestamp(event.get("ingested_at"), "ingested_at")
        if not published <= first_seen <= ingested:
            return True
        if decision_at is not None and max(published, first_seen, ingested) > decision_at:
            return True
        if event.get("event_type") in SCHEDULED_EVENT_TYPES:
            parse_timestamp(event.get("event_at"), "event_at")
        if event.get("revision_state") == "revised":
            superseded = parse_timestamp(
                event.get("superseded_published_at"), "superseded_published_at"
            )
            if superseded >= published:
                return True
    except ContractError:
        return True
    return False


def condition_matches(rule: dict[str, Any], event: dict[str, Any], decision_at: datetime, mode: str) -> bool:
    condition = rule["condition"]
    kind = condition["kind"]
    if kind == "critical_invalid":
        return _critical_invalid(event, decision_at)
    if _critical_invalid(event, decision_at):
        return False
    if kind == "unresolved_live":
        return mode == "future_live" and bool(event.get("unresolved_dependencies"))
    if kind == "field_equals":
        return event.get(condition["field"]) == condition["value"]
    if kind == "field_in":
        return event.get(condition["field"]) in condition["values"]
    if kind == "all_equals":
        return all(event.get(key) == value for key, value in condition["fields"].items())
    if kind == "window":
        if event.get("event_type") not in condition["event_types"]:
            return False
        delta = _seconds_from_event(event, decision_at)
        return condition["start_seconds"] <= delta <= condition["end_seconds"]
    if kind == "freshness":
        if event.get("event_type") not in condition["event_types"]:
            return False
        published = parse_timestamp(event["published_at"], "published_at")
        age = int((decision_at - published).total_seconds())
        operator = condition["operator"]
        limit = condition["seconds"]
        return age <= limit if operator == "lte" else age > limit
    if kind == "social_prohibited":
        return event.get("event_type") in {"ceo_company_social", "x_social_sentiment"} and bool(
            event.get(condition["field"])
        )
    if kind == "social_freshness":
        if (
            event.get("event_type") not in {"ceo_company_social", "x_social_sentiment"}
            or event.get("source_trust") != condition["source_trust"]
            or event.get("verification_state") != condition["verification_state"]
        ):
            return False
        published = parse_timestamp(event["published_at"], "published_at")
        age = int((decision_at - published).total_seconds())
        return age <= condition["seconds"] if condition["operator"] == "lte" else age > condition["seconds"]
    raise ContractError(f"unsupported condition kind: {kind}")


CONDITION_KINDS = {
    "critical_invalid",
    "unresolved_live",
    "field_equals",
    "field_in",
    "all_equals",
    "window",
    "freshness",
    "social_prohibited",
    "social_freshness",
}


def evaluate(policy: dict[str, Any], vector: dict[str, Any]) -> dict[str, Any]:
    """Evaluate fixture events with stable ordering and downward-only effects."""
    validate_policy(policy)
    validate_vector(vector)
    decision_at = parse_timestamp(vector["decision_at"], "decision_at")
    events = sorted(vector["events"], key=canonical_json)
    mode = "research"
    for event in events:
        if isinstance(event, dict) and event.get("mode") == "future_live":
            mode = "future_live"
            break
    matches: dict[str, dict[str, Any]] = {}
    for event in events or [{}]:
        for rule in policy["rules"]:
            if condition_matches(rule, event, decision_at, mode):
                matches[rule["rule_id"]] = rule
    ordered = sorted(matches.values(), key=lambda item: item["priority"])
    if not ordered:
        return {
            "severity": "S0",
            "action": "informational",
            "reason_codes": [],
            "direction_effect": "none",
            "confidence_delta_max": 0,
            "size_multiplier_max": 1.0,
        }
    top = ordered[0]
    restrictive = any(item["action"] in {"reduce_risk", "trade_block", "paper_only", "emergency_halt"} for item in ordered)
    return {
        "severity": top["severity"],
        "action": top["action"],
        "reason_codes": [item["reason_code"] for item in ordered],
        "direction_effect": "none",
        "confidence_delta_max": 0,
        "size_multiplier_max": 0.0 if top["action"] in {"trade_block", "paper_only", "emergency_halt"} else (0.5 if restrictive else 1.0),
    }


def contract_digest(policy: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(policy).encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_artifact_manifest(manifest: dict[str, Any], root: Path = ROOT) -> None:
    expected_fields = {"manifest_version", "algorithm", "artifacts"}
    if not isinstance(manifest, dict) or set(manifest) != expected_fields:
        raise ContractError("artifact manifest fields are invalid")
    if manifest["manifest_version"] != "1.0.0" or manifest["algorithm"] != "sha256":
        raise ContractError("unsupported artifact manifest")
    artifacts = manifest["artifacts"]
    expected_names = {"policy.json", "policy.schema.json", "test_vectors.json"}
    if not isinstance(artifacts, dict) or set(artifacts) != expected_names:
        raise ContractError("artifact manifest membership is invalid")
    for name, expected_digest in artifacts.items():
        if (
            not isinstance(expected_digest, str)
            or len(expected_digest) != 64
            or any(character not in "0123456789abcdef" for character in expected_digest)
        ):
            raise ContractError(f"{name}: invalid sha256 digest")
        if file_digest(root / name) != expected_digest:
            raise ContractError(f"{name}: artifact hash mismatch")
