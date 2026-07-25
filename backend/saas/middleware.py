from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from monitoring import record_monitoring_event


class RateLimitReadyMiddleware(BaseHTTPMiddleware):
    """Attach request metadata and record sanitized private-beta failures."""

    async def dispatch(self, request, call_next):
        request.state.rate_limit_scope = request.client.host if request.client else "unknown"
        try:
            response = await call_next(request)
        except Exception:
            await run_in_threadpool(
                record_monitoring_event,
                "backend_error",
                "An unhandled backend request error occurred.",
                severity="critical",
                path=request.url.path,
                method=request.method,
                status_code=500,
            )
            raise

        event_type = None
        if response.status_code == 401:
            event_type = "failed_auth"
        elif (
            response.status_code >= 400
            and "/paper-trading" in request.url.path
        ):
            event_type = "failed_paper_trade"
        elif response.status_code >= 400 and request.url.path.startswith(
            ("/scan", "/briefing", "/stocks", "/analysis", "/trade-plan")
        ):
            event_type = "failed_market_data"
        elif response.status_code >= 500:
            event_type = "backend_error"

        if event_type and request.url.path != "/me/monitoring/frontend":
            await run_in_threadpool(
                record_monitoring_event,
                event_type,
                f"Request failed with status {response.status_code}.",
                severity=(
                    "critical" if response.status_code >= 500 else "warning"
                ),
                path=request.url.path,
                method=request.method,
                status_code=response.status_code,
            )
        return response
