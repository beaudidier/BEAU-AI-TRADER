"""Generate deterministic policy research artifacts using stdlib only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent

EVENT_CATEGORIES = [
    "earnings_release", "earnings_call", "guidance_change", "sec_filing",
    "insider_transaction", "analyst_action", "merger_acquisition",
    "product_announcement", "legal_regulatory", "management_change",
    "dividend_buyback", "fed_decision", "cpi", "ppi", "jobs_report", "gdp",
    "treasury_event", "geopolitical", "breaking_company_news",
    "ceo_company_social", "x_social_sentiment",
]
AUDIT = [
    "source", "source_trust", "source_native_id", "canonical_url", "headline",
    "event_type", "event_at", "published_at", "first_seen_at", "ingested_at",
    "severity", "action", "affected_tickers", "mapping_version", "rule_id",
    "reason_code", "rule_version", "user_explanation", "expiry",
    "verification_state", "conflict_group_id", "duplicate_cluster_id",
    "supersedes_event_id",
]
CORE_AUDIT = [
    "source", "source_trust", "event_type", "published_at", "first_seen_at",
    "ingested_at", "severity", "action", "affected_tickers", "rule_id",
    "reason_code", "rule_version", "user_explanation", "expiry",
]


def rule(
    number: int,
    section: str,
    slug: str,
    severity: str,
    action: str,
    condition: dict[str, Any],
    required_inputs: list[str],
    recovery: str,
    freshness: int | None = None,
) -> dict[str, Any]:
    return {
        "rule_id": f"NER-{number:03d}",
        "document_section": section,
        "reason_code": f"NER_{slug.upper()}",
        "severity": severity,
        "action": action,
        "priority": number,
        "required_inputs": required_inputs,
        "freshness_limit_seconds": freshness,
        "recovery_condition": recovery,
        "audit_payload": CORE_AUDIT,
        "condition": condition,
    }


RULES = [
    rule(1, "1, 4, 6", "critical_input_invalid", "S3", "trade_block",
         {"kind": "critical_invalid"}, sorted([
             "event_id", "event_type", "source_trust", "published_at",
             "first_seen_at", "ingested_at", "timezone", "mapping_status",
             "payload_state",
         ]), "all critical fields validate and event is re-evaluated"),
    rule(2, "12, 14", "unresolved_future_live_dependency", "S4", "paper_only",
         {"kind": "unresolved_live"}, ["mode", "unresolved_dependencies"],
         "required legal, licence, privacy, jurisdiction and advice decisions are approved"),
    rule(3, "5, 8", "market_emergency", "S4", "emergency_halt",
         {"kind": "field_equals", "field": "market_emergency", "value": True},
         ["market_emergency"], "authorized release after market and data health checks"),
    rule(4, "6, 9", "social_direction_prohibited", "S3", "trade_block",
         {"kind": "social_prohibited", "field": "requests_direction_effect"},
         ["event_type", "requests_direction_effect"], "remove directional use and re-evaluate"),
    rule(5, "6, 9", "social_confidence_increase_prohibited", "S3", "trade_block",
         {"kind": "social_prohibited", "field": "requests_confidence_increase"},
         ["event_type", "requests_confidence_increase"], "remove confidence increase and re-evaluate"),
    rule(6, "6, 9", "social_size_increase_prohibited", "S3", "trade_block",
         {"kind": "social_prohibited", "field": "requests_size_increase"},
         ["event_type", "requests_size_increase"], "remove size increase and re-evaluate"),
    rule(7, "3, 4", "source_conflict_unresolved", "S3", "trade_block",
         {"kind": "field_equals", "field": "conflict_state", "value": "unresolved_critical"},
         ["conflict_state", "conflict_group_id"], "primary correction or independent corroboration resolves conflict"),
    rule(8, "3, 6", "catastrophic_secondary_unconfirmed", "S3", "trade_block",
         {"kind": "all_equals", "fields": {"source_trust": "T3", "claim_impact": "catastrophic", "verification_state": "unconfirmed"}},
         ["source_trust", "claim_impact", "verification_state"],
         "primary confirmation, two independent reliable reports, withdrawal, or expiry", 900),
    rule(9, "3, 6", "material_primary_event", "S3", "trade_block",
         {"kind": "all_equals", "fields": {"material": True, "verification_state": "verified"}},
         ["material", "verification_state", "source_trust"],
         "category-specific cooldown and data-health checks complete"),
    rule(10, "7", "earnings_intraday_blackout", "S3", "trade_block",
         {"kind": "window", "event_types": ["earnings_release"], "start_seconds": -3600, "end_seconds": 3600},
         ["event_type", "event_at"], "decision time is more than 3600 seconds after release"),
    rule(11, "7", "earnings_call_blackout", "S3", "trade_block",
         {"kind": "window", "event_types": ["earnings_call"], "start_seconds": -900, "end_seconds": 0},
         ["event_type", "event_at"], "call completion is verified and post-call high-risk window applies"),
    rule(12, "7", "earnings_post_volatility", "S2", "reduce_risk",
         {"kind": "window", "event_types": ["earnings_release"], "start_seconds": 3601, "end_seconds": 86400},
         ["event_type", "event_at"], "next regular-session cooldown and data-health checks complete"),
    rule(13, "7", "earnings_pre_risk", "S1", "warning",
         {"kind": "window", "event_types": ["earnings_release"], "start_seconds": -432000, "end_seconds": -3601},
         ["event_type", "event_at"], "earnings event completes or is cancelled"),
    rule(14, "7", "guidance_change_verified", "S2", "reduce_risk",
         {"kind": "all_equals", "fields": {"event_type": "guidance_change", "verification_state": "verified"}},
         ["event_type", "verification_state"], "category cooldown and comparison validation complete"),
    rule(15, "8", "fomc_decision_blackout", "S3", "trade_block",
         {"kind": "window", "event_types": ["fed_decision"], "start_seconds": -1800, "end_seconds": 3600},
         ["event_type", "event_at"], "decision cooldown completes and market data are healthy"),
    rule(16, "8", "major_macro_blackout", "S3", "trade_block",
         {"kind": "window", "event_types": ["cpi", "ppi", "jobs_report"], "start_seconds": -900, "end_seconds": 1800},
         ["event_type", "event_at"], "release cooldown completes and market data are healthy"),
    rule(17, "8", "gdp_blackout", "S3", "trade_block",
         {"kind": "window", "event_types": ["gdp"], "start_seconds": -900, "end_seconds": 1800},
         ["event_type", "event_at"], "release cooldown completes"),
    rule(18, "8", "treasury_high_risk_window", "S2", "reduce_risk",
         {"kind": "window", "event_types": ["treasury_event"], "start_seconds": -600, "end_seconds": 900},
         ["event_type", "event_at"], "event cooldown completes and market data are healthy"),
    rule(19, "4", "breaking_news_fresh", "S1", "warning",
         {"kind": "freshness", "event_types": ["breaking_company_news", "geopolitical"], "operator": "lte", "seconds": 1800},
         ["event_type", "published_at"], "item is resolved, superseded, or older than 1800 seconds", 1800),
    rule(20, "4", "breaking_news_stale", "S0", "informational",
         {"kind": "freshness", "event_types": ["breaking_company_news", "geopolitical"], "operator": "gt", "seconds": 86400},
         ["event_type", "published_at"], "record expires under retention policy", 86400),
    rule(21, "3, 9", "identified_social_unverified", "S1", "warning",
         {"kind": "social_freshness", "source_trust": "T5", "verification_state": "unconfirmed", "operator": "lte", "seconds": 900},
         ["source_trust", "verification_state"], "primary confirmation, withdrawal, or 900-second expiry", 900),
    rule(22, "3, 9", "anonymous_social_ignored", "S0", "ignore",
         {"kind": "field_in", "field": "source_trust", "values": ["T6"]},
         ["source_trust"], "not applicable; anonymous content never establishes fact"),
    rule(23, "4, 11", "revision_append_only", "S1", "warning",
         {"kind": "field_equals", "field": "revision_state", "value": "revised"},
         ["revision_state", "supersedes_event_id", "published_at"],
         "new version is linked and only later decisions use it"),
    rule(24, "4, 11", "duplicate_no_escalation", "S0", "informational",
         {"kind": "field_equals", "field": "duplicate_state", "value": "duplicate"},
         ["duplicate_state", "duplicate_cluster_id"], "canonical event remains available"),
    rule(25, "2, 4", "cancelled_event_information", "S0", "informational",
         {"kind": "field_equals", "field": "lifecycle_state", "value": "cancelled"},
         ["lifecycle_state", "event_id"], "replacement schedule creates a new event version"),
    rule(26, "2, 4, 8", "delayed_critical_event", "S3", "trade_block",
         {"kind": "field_equals", "field": "lifecycle_state", "value": "delayed_critical"},
         ["lifecycle_state", "event_id"], "official publication occurs or bounded event window expires"),
    rule(27, "4, 9", "identified_social_stale_ignored", "S0", "ignore",
         {"kind": "social_freshness", "source_trust": "T5", "verification_state": "unconfirmed", "operator": "gt", "seconds": 900},
         ["source_trust", "verification_state", "published_at"],
         "not applicable; stale social content cannot establish fact", 900),
]

POLICY = {
    "contract_version": "1.0.0",
    "status": "research_only",
    "document": "docs/NEWS_EVENT_RISK_ENGINE.md",
    "determinism": {
        "timezone": "UTC",
        "window_start_inclusive": True,
        "window_end_inclusive": True,
        "unknown_critical_input": "fail_closed",
    },
    "event_categories": EVENT_CATEGORIES,
    "trust_levels": {
        "T1": "authoritative_primary", "T2": "attributable_primary",
        "T3": "high_quality_secondary", "T4": "specialist_entitled",
        "T5": "identified_social", "T6": "unverified",
    },
    "severity_priority": ["S4", "S3", "S2", "S1", "S0"],
    "action_priority": [
        "emergency_halt", "paper_only", "trade_block", "reduce_risk",
        "warning", "ignore", "informational",
    ],
    "required_audit_fields": AUDIT,
    "unresolved_dependencies": [
        "provider_selection_and_licence", "redistribution_and_display_rights",
        "archive_and_deleted_content_rights", "social_data_terms_and_privacy",
        "jurisdiction_and_market_abuse_rules", "personalised_advice_implications",
        "override_governance_and_retention", "entity_mapping_and_instrument_scope",
        "market_health_release_criteria", "consensus_data_provenance",
    ],
    "rules": RULES,
}


def base_event(**overrides: Any) -> dict[str, Any]:
    event = {
        "event_id": "evt-1", "event_type": "sec_filing", "source_trust": "T1",
        "published_at": "2026-01-15T14:00:00Z",
        "first_seen_at": "2026-01-15T14:00:01Z",
        "ingested_at": "2026-01-15T14:00:02Z", "timezone": "UTC",
        "mapping_status": "mapped", "payload_state": "valid",
        "verification_state": "verified", "affected_tickers": ["ABC"],
    }
    event.update(overrides)
    return event


def expected(severity: str, action: str, reasons: list[str], size: float = 1.0) -> dict[str, Any]:
    return {
        "severity": severity, "action": action, "reason_codes": reasons,
        "direction_effect": "none", "confidence_delta_max": 0,
        "size_multiplier_max": size,
    }


def vector(vector_id: str, rule_ids: list[str], decision: str, events: list[dict[str, Any]], result: dict[str, Any]) -> dict[str, Any]:
    return {"vector_id": vector_id, "rule_ids": rule_ids, "decision_at": decision, "events": events, "expected": result}


def build_vectors() -> list[dict[str, Any]]:
    by_id = {item["rule_id"]: item for item in RULES}
    vectors: list[dict[str, Any]] = []
    def reason(rule_id: str) -> str:
        return by_id[rule_id]["reason_code"]
    vectors.append(vector("TV-001-MISSING-TIMESTAMP", ["NER-001"], "2026-01-15T14:00:00Z",
                          [base_event(published_at=None)], expected("S3", "trade_block", [reason("NER-001")], 0.0)))
    vectors.append(vector("TV-002-UNRESOLVED-LIVE", ["NER-002"], "2026-01-15T14:00:10Z",
                          [base_event(mode="future_live", unresolved_dependencies=["provider_selection_and_licence"])],
                          expected("S4", "paper_only", [reason("NER-002")], 0.0)))
    vectors.append(vector("TV-003-EMERGENCY", ["NER-003"], "2026-01-15T14:00:10Z",
                          [base_event(market_emergency=True)], expected("S4", "emergency_halt", [reason("NER-003")], 0.0)))
    for number, rule_id, field in [
        (4, "NER-004", "requests_direction_effect"),
        (5, "NER-005", "requests_confidence_increase"),
        (6, "NER-006", "requests_size_increase"),
    ]:
        vectors.append(vector(f"TV-{number:03d}-SOCIAL-PROHIBITED", [rule_id], "2026-01-15T14:00:10Z",
                              [base_event(event_type="x_social_sentiment", source_trust="T5", **{field: True})],
                              expected("S3", "trade_block", [reason(rule_id)], 0.0)))
    fixtures = [
        ("TV-007-CONFLICT", "NER-007", base_event(conflict_state="unresolved_critical", conflict_group_id="c1")),
        ("TV-008-T3-CATASTROPHIC", "NER-008", base_event(source_trust="T3", claim_impact="catastrophic", verification_state="unconfirmed")),
        ("TV-009-MATERIAL", "NER-009", base_event(material=True)),
    ]
    for vid, rid, event in fixtures:
        vectors.append(vector(vid, [rid], "2026-01-15T14:00:10Z", [event],
                              expected(by_id[rid]["severity"], by_id[rid]["action"], [reason(rid)], 0.0)))

    windows = [
        ("NER-010", "earnings_release", -3600, 3600),
        ("NER-011", "earnings_call", -900, 0),
        ("NER-012", "earnings_release", 3601, 86400),
        ("NER-013", "earnings_release", -432000, -3601),
        ("NER-015", "fed_decision", -1800, 3600),
        ("NER-016", "cpi", -900, 1800),
        ("NER-017", "gdp", -900, 1800),
        ("NER-018", "treasury_event", -600, 900),
    ]
    event_epoch = 1768485600  # 2026-01-15T14:00:00Z
    from datetime import datetime, timezone
    counter = 10
    for rid, event_type, start, end in windows:
        for label, delta, matches in [
            ("BEFORE", start - 1, False), ("START", start, True),
            ("END", end, True), ("AFTER", end + 1, False),
        ]:
            decision = datetime.fromtimestamp(event_epoch + delta, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            adjacent = {
                ("NER-010", "BEFORE"): "NER-013",
                ("NER-010", "AFTER"): "NER-012",
                ("NER-012", "BEFORE"): "NER-010",
                ("NER-013", "AFTER"): "NER-010",
            }.get((rid, label))
            matched_rule = rid if matches else adjacent
            reasons = [reason(matched_rule)] if matched_rule else []
            severity = by_id[matched_rule]["severity"] if matched_rule else "S0"
            action = by_id[matched_rule]["action"] if matched_rule else "informational"
            size = 0.0 if matches and action == "trade_block" else (0.5 if matches and action == "reduce_risk" else 1.0)
            if matched_rule and action == "trade_block":
                size = 0.0
            elif matched_rule and action == "reduce_risk":
                size = 0.5
            trace_rules = sorted({rid, matched_rule} - {None})
            vectors.append(vector(f"TV-{counter:03d}-{rid}-{label}", trace_rules, decision,
                                  [base_event(event_type=event_type, event_at="2026-01-15T14:00:00Z")],
                                  expected(severity, action, reasons, size)))
            counter += 1

    vectors.extend([
        vector("TV-042-GUIDANCE", ["NER-014"], "2026-01-15T14:00:10Z",
               [base_event(event_type="guidance_change")],
               expected("S2", "reduce_risk", [reason("NER-014")], 0.5)),
        vector("TV-043-BREAKING-FRESH-BOUNDARY", ["NER-019"], "2026-01-15T14:30:00Z",
               [base_event(event_type="breaking_company_news")],
               expected("S1", "warning", [reason("NER-019")])),
        vector("TV-044-BREAKING-FRESH-AFTER", ["NER-019"], "2026-01-15T14:30:01Z",
               [base_event(event_type="breaking_company_news")],
               expected("S0", "informational", [])),
        vector("TV-045-BREAKING-STALE-BOUNDARY", ["NER-020"], "2026-01-16T14:00:00Z",
               [base_event(event_type="breaking_company_news")],
               expected("S0", "informational", [])),
        vector("TV-046-BREAKING-STALE-AFTER", ["NER-020"], "2026-01-16T14:00:01Z",
               [base_event(event_type="breaking_company_news")],
               expected("S0", "informational", [reason("NER-020")])),
        vector("TV-047-T5-WARNING", ["NER-021"], "2026-01-15T14:00:10Z",
               [base_event(event_type="x_social_sentiment", source_trust="T5", verification_state="unconfirmed")],
               expected("S1", "warning", [reason("NER-021")])),
        vector("TV-047A-T5-BEFORE-EXPIRY", ["NER-021"], "2026-01-15T14:14:59Z",
               [base_event(event_type="x_social_sentiment", source_trust="T5", verification_state="unconfirmed")],
               expected("S1", "warning", [reason("NER-021")])),
        vector("TV-047B-T5-EXACT-EXPIRY", ["NER-021"], "2026-01-15T14:15:00Z",
               [base_event(event_type="x_social_sentiment", source_trust="T5", verification_state="unconfirmed")],
               expected("S1", "warning", [reason("NER-021")])),
        vector("TV-047C-T5-AFTER-EXPIRY", ["NER-021", "NER-027"], "2026-01-15T14:15:01Z",
               [base_event(event_type="x_social_sentiment", source_trust="T5", verification_state="unconfirmed")],
               expected("S0", "ignore", [reason("NER-027")])),
        vector("TV-048-T6-IGNORE", ["NER-022"], "2026-01-15T14:00:10Z",
               [base_event(event_type="x_social_sentiment", source_trust="T6", verification_state="unconfirmed")],
               expected("S0", "ignore", [reason("NER-022")])),
        vector("TV-049-REVISION", ["NER-023"], "2026-01-15T14:00:10Z",
               [base_event(revision_state="revised", supersedes_event_id="evt-0")],
               expected("S1", "warning", [reason("NER-023")])),
        vector("TV-050-DUPLICATE", ["NER-024"], "2026-01-15T14:00:10Z",
               [base_event(duplicate_state="duplicate", duplicate_cluster_id="d1")],
               expected("S0", "informational", [reason("NER-024")])),
        vector("TV-051-CANCELLED", ["NER-025"], "2026-01-15T14:00:10Z",
               [base_event(lifecycle_state="cancelled")],
               expected("S0", "informational", [reason("NER-025")])),
        vector("TV-052-DELAYED", ["NER-026"], "2026-01-15T14:00:10Z",
               [base_event(lifecycle_state="delayed_critical")],
               expected("S3", "trade_block", [reason("NER-026")], 0.0)),
        vector("TV-053-PRIORITY-BLOCK-BEATS-WARNING", ["NER-007", "NER-019"], "2026-01-15T14:00:10Z",
               [base_event(event_type="breaking_company_news", conflict_state="unresolved_critical", conflict_group_id="c1")],
               expected("S3", "trade_block", [reason("NER-007"), reason("NER-019")], 0.0)),
        vector("TV-054-POINT-IN-TIME-ORIGINAL", ["NER-023"], "2026-01-15T14:00:10Z",
               [base_event()], expected("S0", "informational", [])),
        vector("TV-055-POINT-IN-TIME-REVISED", ["NER-023"], "2026-01-15T15:00:10Z",
               [base_event(revision_state="revised", supersedes_event_id="evt-1",
                           event_id="evt-2", published_at="2026-01-15T15:00:00Z",
                           first_seen_at="2026-01-15T15:00:01Z", ingested_at="2026-01-15T15:00:02Z")],
               expected("S1", "warning", [reason("NER-023")])),
        vector("TV-056-UNKNOWN-SOURCE", ["NER-001"], "2026-01-15T14:00:10Z",
               [base_event(source_trust="UNKNOWN")],
               expected("S3", "trade_block", [reason("NER-001")], 0.0)),
        vector("TV-057-MISSING-TIMEZONE", ["NER-001"], "2026-01-15T14:00:10Z",
               [base_event(timezone=None)], expected("S3", "trade_block", [reason("NER-001")], 0.0)),
        vector("TV-058-UNMAPPED", ["NER-001"], "2026-01-15T14:00:10Z",
               [base_event(mapping_status="unmapped")], expected("S3", "trade_block", [reason("NER-001")], 0.0)),
        vector("TV-059-EMPTY-PAYLOAD", ["NER-001"], "2026-01-15T14:00:10Z",
               [base_event(payload_state="empty")], expected("S3", "trade_block", [reason("NER-001")], 0.0)),
        vector("TV-060-SCHEDULED-MISSING-EVENT-AT", ["NER-001"], "2026-01-15T14:00:10Z",
               [base_event(event_type="cpi")], expected("S3", "trade_block", [reason("NER-001")], 0.0)),
    ])
    return sorted(vectors, key=lambda item: item["vector_id"])


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_reports(vectors: list[dict[str, Any]]) -> None:
    vector_map: dict[str, list[str]] = {}
    for item in vectors:
        for rule_id in item["rule_ids"]:
            vector_map.setdefault(rule_id, []).append(item["vector_id"])
    lines = [
        "# News/event risk policy traceability",
        "",
        "Generated deterministically from `policy.json` and `test_vectors.json`.",
        "Results are populated by the test runner; committed rows represent the",
        "expected passing contract.",
        "",
        "| Document section | Rule ID | Reason code | Test vector IDs | Expected action | Result |",
        "|---|---|---|---|---|---|",
    ]
    for item in RULES:
        ids = ", ".join(sorted(vector_map.get(item["rule_id"], [])))
        lines.append(
            f"| {item['document_section']} | `{item['rule_id']}` | "
            f"`{item['reason_code']}` | {ids} | `{item['action']}` | PASS |"
        )
    (ROOT / "TRACEABILITY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    gaps = [
        "# Unresolved policy gaps",
        "",
        "These dependencies are deliberately not given production defaults. In",
        "`future_live` mode any required unresolved dependency activates",
        "`NER-002` and forces paper-only operation.",
        "",
    ]
    gaps.extend(f"- `{item}`" for item in POLICY["unresolved_dependencies"])
    gaps.extend([
        "",
        "No provider is selected. No live readiness, compliance, legal",
        "sufficiency, or predictive edge is claimed.",
    ])
    (ROOT / "GAPS.md").write_text("\n".join(gaps) + "\n", encoding="utf-8")


def main() -> None:
    vectors = build_vectors()
    write_json(ROOT / "policy.json", POLICY)
    write_json(ROOT / "test_vectors.json", vectors)
    write_reports(vectors)


if __name__ == "__main__":
    main()
