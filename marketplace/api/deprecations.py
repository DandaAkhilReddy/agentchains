"""Helpers for deprecating legacy v1 endpoints."""

from fastapi import Response

LEGACY_V1_SUNSET = "Sat, 16 May 2026 00:00:00 GMT"
LEGACY_V1_MIGRATION_DOC = (
    "<https://github.com/DandaAkhilReddy/agentchains/blob/master/docs/API_MIGRATION_V2_USD.md>; rel=\"deprecation\""
)


def apply_legacy_v1_deprecation_headers(response: Response) -> None:
    """Attach deprecation metadata for legacy v1 compatibility routes."""
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = LEGACY_V1_SUNSET
    response.headers["Link"] = LEGACY_V1_MIGRATION_DOC
