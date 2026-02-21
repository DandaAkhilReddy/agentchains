"""Pydantic v2 models for all A2UI message types.

Covers agent-to-UI pushes, user responses, and session lifecycle.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── Enums ────────────────────────────────────────────────────────


class A2UIComponentType(str, Enum):
    card = "card"
    table = "table"
    form = "form"
    chart = "chart"
    markdown = "markdown"
    code = "code"
    image = "image"
    alert = "alert"
    steps = "steps"


class A2UIProgressType(str, Enum):
    determinate = "determinate"
    indeterminate = "indeterminate"
    streaming = "streaming"


class A2UIInputType(str, Enum):
    text = "text"
    select = "select"
    number = "number"
    date = "date"
    file = "file"


# ── Agent -> UI messages ─────────────────────────────────────────


class A2UIRenderMessage(BaseModel):
    """Agent pushes a new component to the UI."""

    model_config = ConfigDict(populate_by_name=True)

    component_id: str = Field(..., min_length=1, max_length=100)
    component_type: A2UIComponentType
    data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] | None = None


class A2UIUpdateMessage(BaseModel):
    """Agent patches an existing UI component."""

    model_config = ConfigDict(populate_by_name=True)

    component_id: str = Field(..., min_length=1, max_length=100)
    operation: str = Field(..., pattern=r"^(replace|merge|append)$")
    data: dict[str, Any] = Field(default_factory=dict)


class A2UIRequestInputMessage(BaseModel):
    """Agent requests input from the user."""

    model_config = ConfigDict(populate_by_name=True)

    request_id: str = Field(..., min_length=1, max_length=100)
    input_type: A2UIInputType
    prompt: str = Field(..., min_length=1, max_length=1000)
    options: list[str] | None = None
    validation: dict[str, Any] | None = None


class A2UIConfirmMessage(BaseModel):
    """Agent requests approval from the user."""

    model_config = ConfigDict(populate_by_name=True)

    request_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    severity: str = Field(default="info", pattern=r"^(info|warning|critical)$")
    timeout_seconds: int = Field(default=30, ge=1, le=300)


class A2UIProgressMessage(BaseModel):
    """Agent streams progress updates to the UI."""

    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(..., min_length=1, max_length=100)
    progress_type: A2UIProgressType
    value: float | None = None
    total: float | None = None
    message: str | None = None


class A2UINavigateMessage(BaseModel):
    """Agent redirects the user."""

    model_config = ConfigDict(populate_by_name=True)

    url: str = Field(..., min_length=1, max_length=2000)
    new_tab: bool = False


class A2UINotifyMessage(BaseModel):
    """Agent sends a toast notification."""

    model_config = ConfigDict(populate_by_name=True)

    level: str = Field(default="info", pattern=r"^(info|success|warning|error)$")
    title: str = Field(..., min_length=1, max_length=255)
    message: str | None = None
    duration_ms: int = Field(default=5000, ge=0, le=60000)


# ── UI -> Agent messages ─────────────────────────────────────────


class A2UIInitRequest(BaseModel):
    """UI sends initialization request to the agent."""

    model_config = ConfigDict(populate_by_name=True)

    client_info: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)


class A2UIInitResponse(BaseModel):
    """Response to an initialization request."""

    model_config = ConfigDict(populate_by_name=True)

    session_id: str
    capabilities: dict[str, Any] = Field(default_factory=dict)
    version: str


class A2UIUserResponse(BaseModel):
    """User sends an input value back to the agent."""

    model_config = ConfigDict(populate_by_name=True)

    request_id: str = Field(..., min_length=1, max_length=100)
    value: Any = None


class A2UIUserApproval(BaseModel):
    """User approves or rejects an agent request."""

    model_config = ConfigDict(populate_by_name=True)

    request_id: str = Field(..., min_length=1, max_length=100)
    approved: bool
    reason: str | None = None


class A2UIUserCancel(BaseModel):
    """User cancels an agent operation."""

    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(..., min_length=1, max_length=100)
