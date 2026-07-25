"""Best-effort private-beta production monitoring without sensitive payloads."""

from __future__ import annotations

import sys
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Literal

from saas.config import get_settings

try:
    from supabase import create_client
except ImportError:
    create_client = None


EventType = Literal[
    "frontend_error",
    "backend_error",
    "failed_auth",
    "failed_market_data",
    "failed_paper_trade",
    "scheduler_failure",
]

logger = logging.getLogger("beau.private_beta.monitoring")

_SENSITIVE_MONITORING_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+\S+"),
    re.compile(r"\bsb_(?:secret|publishable)_[A-Za-z0-9_-]+\b"),
    re.compile(
        r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
        r"\.[A-Za-z0-9_-]{10,}\b"
    ),
    re.compile(
        r"(?i)\b(access_token|refresh_token|api_?key|password|token)"
        r"=([^&\s]+)"
    ),
)


def sanitize_monitoring_text(message: str) -> str:
    """Remove common credential shapes before an event reaches storage."""

    sanitized = message
    for pattern in _SENSITIVE_MONITORING_PATTERNS:
        sanitized = pattern.sub(
            lambda match: (
                f"{match.group(1)}=[REDACTED]"
                if match.lastindex == 2
                else "[REDACTED]"
            ),
            sanitized,
        )
    return sanitized[:1000]


def sanitize_monitoring_path(path: str | None) -> str | None:
    """Redact private invite tokens from monitored request paths."""

    if not path:
        return None
    sanitized = re.sub(
        r"(?i)(/invite/)[^/?#\s]+",
        r"\1[REDACTED]",
        path,
    )
    return sanitized[:500]


def record_monitoring_event(
    event_type: EventType,
    message: str,
    *,
    severity: Literal["warning", "error", "critical"] = "error",
    user_id: str | None = None,
    path: str | None = None,
    method: str | None = None,
    status_code: int | None = None,
    context: dict[str, Any] | None = None,
) -> bool:
    """Store a sanitized operational event; monitoring must never break the app."""

    values = {
        "event_type": event_type,
        "severity": severity,
        "user_id": user_id,
        "path": sanitize_monitoring_path(path),
        "method": (method or "")[:20] or None,
        "status_code": status_code,
        "message": sanitize_monitoring_text(message),
        "context": context or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    settings = get_settings()
    if (
        create_client is None
        or not settings.supabase_url
        or not settings.supabase_service_role_key
    ):
        logger.warning("private_beta_event %s", json.dumps(values, sort_keys=True))
        return True
    try:
        create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        ).table("beta_monitoring_events").insert(values).execute()
        return True
    except Exception:
        logger.exception(
            "private_beta_monitoring_storage_failed event_type=%s",
            event_type,
        )
        return False


def _report_scheduler_failure() -> int:
    recorded = record_monitoring_event(
        "scheduler_failure",
        "The scheduled forward-validation workflow failed.",
        severity="critical",
        path="github-actions/forward-validation",
        method="SCHEDULE",
    )
    return 0 if recorded else 1


if __name__ == "__main__":
    if sys.argv[1:] == ["scheduler-failure"]:
        raise SystemExit(_report_scheduler_failure())
    raise SystemExit("Usage: python -m monitoring scheduler-failure")
