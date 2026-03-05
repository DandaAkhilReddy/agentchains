"""Prometheus /metrics endpoint — serves metrics in Prometheus text format."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter(tags=["monitoring"])


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    """Return Prometheus metrics in text exposition format."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
