"""Builder APIs for developer project templates and publishing."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.creator_auth import get_current_creator_id
from marketplace.database import get_db
from marketplace.schemas.dual_layer import (
    BuilderProjectCreateRequest,
    BuilderProjectListResponse,
    BuilderProjectResponse,
    BuilderPublishResponse,
    BuilderTemplateResponse,
)
from marketplace.services import dual_layer_service

router = APIRouter(prefix="/builder", tags=["builder-v2"])


@router.get("/templates", response_model=list[BuilderTemplateResponse])
async def list_builder_templates_v2():
    return dual_layer_service.list_builder_templates()


@router.post("/projects", response_model=BuilderProjectResponse, status_code=201)
async def create_builder_project_v2(
    req: BuilderProjectCreateRequest,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    creator_id = get_current_creator_id(authorization)
    try:
        return await dual_layer_service.create_builder_project(
            db,
            creator_id=creator_id,
            template_key=req.template_key,
            title=req.title,
            config=req.config,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects", response_model=BuilderProjectListResponse)
async def list_builder_projects_v2(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    creator_id = get_current_creator_id(authorization)
    projects = await dual_layer_service.list_builder_projects(
        db, creator_id=creator_id
    )
    return {"total": len(projects), "projects": projects}


@router.post("/projects/{project_id}/publish", response_model=BuilderPublishResponse)
async def publish_builder_project_v2(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    creator_id = get_current_creator_id(authorization)
    try:
        return await dual_layer_service.publish_builder_project(
            db,
            creator_id=creator_id,
            project_id=project_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
