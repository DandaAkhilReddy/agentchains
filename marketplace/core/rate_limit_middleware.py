"""Rate limiting middleware for REST API endpoints."""

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from marketplace.config import settings
from marketplace.core.rate_limiter import rate_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    SKIP_PATHS = {"/api/v1/health", "/mcp/health", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.SKIP_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        key, authenticated = self._extract_key(request)
        allowed, headers = rate_limiter.check(key, authenticated)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": int(headers.get("Retry-After", "60")),
                },
                headers=headers,
            )

        response: Response = await call_next(request)
        for k, v in headers.items():
            response.headers[k] = v
        return response

    def _extract_key(self, request: Request) -> tuple[str, bool]:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            try:
                payload = jwt.decode(
                    auth[7:],
                    settings.jwt_secret_key,
                    algorithms=[settings.jwt_algorithm],
                )
                return f"agent:{payload.get('sub', 'unknown')}", True
            except JWTError:
                pass
        # Fall back to IP
        client = request.client
        ip = client.host if client else "unknown"
        # Only trust X-Forwarded-For from localhost/docker (reverse proxy)
        TRUSTED_PROXIES = {"127.0.0.1", "::1", "localhost", "172.17.0.1"}
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded and ip in TRUSTED_PROXIES:
            ip = forwarded.split(",")[0].strip()
        return f"ip:{ip}", False
