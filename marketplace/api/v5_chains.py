"""Chain Registry v5 API — chain template CRUD, execution, forking, and provenance."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="", tags=["chains"])
