"""Public, secret-free production readiness checks for the private beta."""

from __future__ import annotations

import json
import os
import ssl
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


FRONTEND_URL = os.getenv(
    "BETA_FRONTEND_URL",
    "https://beau-ai-trader.vercel.app",
).rstrip("/")
BACKEND_URL = os.getenv(
    "BETA_BACKEND_URL",
    "https://beau-ai-trader-api.vercel.app",
).rstrip("/")
SUPABASE_URL = os.getenv(
    "BETA_SUPABASE_URL",
    "https://busjjtpmqgfiniysaxpe.supabase.co",
).rstrip("/")
TIMEOUT_SECONDS = float(os.getenv("BETA_SMOKE_TIMEOUT_SECONDS", "60"))
try:
    import certifi

    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()


@dataclass(frozen=True)
class SmokeResult:
    name: str
    ok: bool
    status: int | None
    message: str
    duration_ms: int


def _request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    request = Request(
        url,
        method=method,
        headers={
            "User-Agent": "BEAU-AI-TRADER-production-smoke/1.0",
            **(headers or {}),
        },
    )
    try:
        with urlopen(
            request,
            timeout=TIMEOUT_SECONDS,
            context=SSL_CONTEXT,
        ) as response:
            return (
                response.status,
                {key.lower(): value for key, value in response.headers.items()},
                response.read(),
            )
    except HTTPError as error:
        return (
            error.code,
            {key.lower(): value for key, value in error.headers.items()},
            error.read(),
        )


def _json(body: bytes) -> Any:
    return json.loads(body.decode("utf-8"))


def _check(
    name: str,
    request: Callable[[], tuple[int, dict[str, str], bytes]],
    validate: Callable[[int, dict[str, str], bytes], str],
    *,
    attempts: int = 2,
) -> SmokeResult:
    started = time.monotonic()
    status: int | None = None
    last_message = "The service did not respond."
    for attempt in range(attempts):
        try:
            status, headers, body = request()
            message = validate(status, headers, body)
            return SmokeResult(
                name,
                True,
                status,
                message,
                round((time.monotonic() - started) * 1000),
            )
        except (AssertionError, KeyError, TypeError, ValueError, URLError) as error:
            last_message = str(error) or "Unexpected response."
            if attempt + 1 < attempts:
                time.sleep(1)
    return SmokeResult(
        name,
        False,
        status,
        last_message,
        round((time.monotonic() - started) * 1000),
    )


def _expect_spa(status: int, _headers: dict[str, str], body: bytes) -> str:
    assert status == 200, f"Expected page status 200, received {status}."
    text = body.decode("utf-8", errors="replace")
    assert 'id="root"' in text, "The application shell is missing."
    return "Application shell loaded."


def _expect_json(
    expected_status: int,
    predicate: Callable[[Any], bool],
    success: str,
) -> Callable[[int, dict[str, str], bytes], str]:
    def validate(status: int, _headers: dict[str, str], body: bytes) -> str:
        assert status == expected_status, (
            f"Expected status {expected_status}, received {status}."
        )
        payload = _json(body)
        assert predicate(payload), "The response shape is not ready for the beta."
        return success

    return validate


def build_checks() -> list[SmokeResult]:
    results: list[SmokeResult] = []

    for route in (
        "/login",
        "/dashboard",
        "/evidence",
        "/forward-validation",
    ):
        results.append(
            _check(
                f"frontend:{route}",
                lambda route=route: _request(f"{FRONTEND_URL}{route}"),
                _expect_spa,
            )
        )

    results.extend(
        [
            _check(
                "backend:health",
                lambda: _request(f"{BACKEND_URL}/"),
                _expect_json(
                    200,
                    lambda payload: payload.get("status") == "running",
                    "Backend is running.",
                ),
            ),
            _check(
                "supabase:auth-health",
                lambda: _request(f"{SUPABASE_URL}/auth/v1/health"),
                lambda status, _headers, _body: (
                    "Supabase Auth is reachable and requires a project key."
                    if status in {200, 401}
                    else (_ for _ in ()).throw(
                        AssertionError(
                            f"Expected Supabase status 200 or 401, received {status}."
                        )
                    )
                ),
            ),
            _check(
                "dashboard:strategies",
                lambda: _request(f"{BACKEND_URL}/strategies"),
                _expect_json(
                    200,
                    lambda payload: isinstance(payload, list)
                    and any(item.get("id") == "swing_trading" for item in payload),
                    "Swing strategy metadata is available.",
                ),
            ),
            _check(
                "dashboard:briefing",
                lambda: _request(f"{BACKEND_URL}/briefing"),
                _expect_json(
                    200,
                    lambda payload: isinstance(payload.get("opportunities"), list),
                    "Dashboard briefing is available.",
                ),
            ),
            _check(
                "dashboard:scanner",
                lambda: _request(
                    f"{BACKEND_URL}/scan?strategy=swing_trading"
                ),
                _expect_json(
                    200,
                    lambda payload: isinstance(payload, list),
                    "Scanner returned a valid result set.",
                ),
            ),
            _check(
                "latest-signals:evidence",
                lambda: _request(
                    f"{FRONTEND_URL}/latest-signals/summary.json"
                ),
                _expect_json(
                    200,
                    lambda payload: isinstance(payload.get("signals"), list),
                    "Latest-signal evidence is available.",
                ),
            ),
            _check(
                "workspace:chart",
                lambda: _request(
                    f"{BACKEND_URL}/stocks/NVDA/history?timeframe=6M"
                ),
                _expect_json(
                    200,
                    lambda payload: bool(payload.get("candles"))
                    and payload.get("ticker") == "NVDA",
                    "Workspace chart data is available.",
                ),
            ),
            _check(
                "workspace:analysis",
                lambda: _request(f"{BACKEND_URL}/analysis/NVDA"),
                _expect_json(
                    200,
                    lambda payload: "overall_score" in payload
                    and "recommendation" in payload,
                    "Workspace analysis is available.",
                ),
            ),
            _check(
                "workspace:trade-plan",
                lambda: _request(f"{BACKEND_URL}/trade-plan/NVDA"),
                _expect_json(
                    200,
                    lambda payload: payload.get("ticker") == "NVDA"
                    and "entry" in payload,
                    "Workspace trade plan is available.",
                ),
            ),
            _check(
                "feedback:auth-guard",
                lambda: _request(f"{BACKEND_URL}/me/feedback"),
                _expect_json(
                    401,
                    lambda payload: bool(payload.get("detail")),
                    "Feedback endpoint is protected and reachable.",
                ),
            ),
            _check(
                "forward-validation:auth-guard",
                lambda: _request(
                    f"{BACKEND_URL}/me/forward-validation/dashboard"
                ),
                _expect_json(
                    401,
                    lambda payload: bool(payload.get("detail")),
                    "Forward-validation endpoint is protected and reachable.",
                ),
            ),
            _check(
                "backend:cors",
                lambda: _request(
                    f"{BACKEND_URL}/strategies",
                    method="OPTIONS",
                    headers={
                        "Origin": FRONTEND_URL,
                        "Access-Control-Request-Method": "GET",
                    },
                ),
                lambda status, headers, _body: (
                    "Production origin accepted."
                    if status in {200, 204}
                    and headers.get("access-control-allow-origin")
                    == FRONTEND_URL
                    else (_ for _ in ()).throw(
                        AssertionError(
                            "The production frontend origin is not allowed."
                        )
                    )
                ),
            ),
        ]
    )
    return results


def main() -> int:
    results = build_checks()
    summary = {
        "status": "passed" if all(result.ok for result in results) else "failed",
        "checks": len(results),
        "passed": sum(result.ok for result in results),
        "failed": sum(not result.ok for result in results),
        "results": [asdict(result) for result in results],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
