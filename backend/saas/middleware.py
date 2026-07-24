from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitReadyMiddleware(BaseHTTPMiddleware):
    """Attach request metadata now; a shared rate-limit store can be added without route changes."""

    async def dispatch(self, request, call_next):
        request.state.rate_limit_scope = request.client.host if request.client else "unknown"
        return await call_next(request)
