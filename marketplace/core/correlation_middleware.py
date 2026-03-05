"""Correlation ID middleware — generates per-request IDs and injects into context vars.

Sets X-Correlation-ID and X-Request-ID headers on all responses.
Extracts agent_id from JWT when present.
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from marketplace.core.structured_logging import (
    agent_id_var,
    correlation_id_var,
    operation_var,
    request_id_var,
)


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Generates correlation/request IDs per request and sets context vars."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Use incoming header or generate new
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Set context vars for structured logging
        correlation_id_token = correlation_id_var.set(correlation_id)
        request_id_token = request_id_var.set(request_id)
        operation_token = operation_var.set(f"{request.method} {request.url.path}")

        # Extract agent_id from JWT if present
        agent_id_token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from marketplace.core.auth import decode_token

                payload = decode_token(auth_header.split(" ", 1)[1])
                agent_id = payload.get("sub", "")
                if agent_id:
                    agent_id_token = agent_id_var.set(agent_id)
            except Exception:
                pass  # Invalid token — agent_id stays empty

        try:
            response: Response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            correlation_id_var.reset(correlation_id_token)
            request_id_var.reset(request_id_token)
            operation_var.reset(operation_token)
            if agent_id_token is not None:
                agent_id_var.reset(agent_id_token)
