"""MCP authentication: validate JWT from MCP initialize handshake."""

from marketplace.core.auth import decode_token
from marketplace.core.exceptions import UnauthorizedError


def validate_mcp_auth(params: dict) -> str:
    """Extract and validate agent_id from MCP initialize params.

    MCP clients pass their JWT in the initialize request's capabilities
    or meta field. Returns agent_id on success, raises on failure.
    """
    # Try multiple locations where clients might pass auth
    token = None

    # Location 1: params.capabilities.auth.token
    caps = params.get("capabilities", {})
    auth = caps.get("auth", {})
    if isinstance(auth, dict):
        token = auth.get("token")

    # Location 2: params.meta.authorization
    if not token:
        meta = params.get("meta", {})
        token = meta.get("authorization", "")
        if token.lower().startswith("bearer "):
            token = token[7:]
        elif not token:
            token = None

    # Location 3: params._auth (convention)
    if not token:
        token = params.get("_auth")

    if not token:
        raise UnauthorizedError("MCP session requires authentication. Pass JWT in initialize params.")

    payload = decode_token(token)
    return payload["sub"]
