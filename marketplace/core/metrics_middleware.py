"""Prometheus metrics middleware — auto-records request count and latency."""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from marketplace.core.metrics import REQUEST_COUNT, REQUEST_LATENCY


def _normalize_path(path: str) -> str:
    """Collapse path parameters to reduce cardinality.

    Replaces UUID-like and numeric segments with placeholders.
    """
    parts = path.strip("/").split("/")
    normalized: list[str] = []
    for part in parts:
        # UUID pattern (8-4-4-4-12 hex)
        if len(part) == 36 and part.count("-") == 4:
            normalized.append("{id}")
        # Pure numeric
        elif part.isdigit():
            normalized.append("{id}")
        else:
            normalized.append(part)
    return "/" + "/".join(normalized)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Records HTTP request count and latency as Prometheus metrics."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip metrics endpoint itself to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        path = _normalize_path(request.url.path)
        start = time.perf_counter()

        response: Response = await call_next(request)

        duration = time.perf_counter() - start
        status_code = str(response.status_code)

        REQUEST_COUNT.labels(method=method, endpoint=path, status_code=status_code).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=path).observe(duration)

        return response
