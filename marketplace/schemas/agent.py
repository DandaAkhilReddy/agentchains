from datetime import datetime

from pydantic import BaseModel, Field


class AgentRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=5000)
    agent_type: str = Field(..., pattern="^(seller|buyer|both)$")
    public_key: str = Field(..., min_length=10, max_length=10_000)
    wallet_address: str = Field(default="", max_length=255)
    capabilities: list[str] = Field(default=[], max_length=50)
    a2a_endpoint: str = Field(default="", max_length=1000)


class AgentRegisterResponse(BaseModel):
    id: str
    name: str
    jwt_token: str
    agent_card_url: str
    created_at: datetime


class AgentUpdateRequest(BaseModel):
    description: str | None = Field(None, max_length=5000)
    wallet_address: str | None = Field(None, max_length=255)
    capabilities: list[str] | None = Field(None, max_length=50)
    a2a_endpoint: str | None = Field(None, max_length=1000)
    status: str | None = Field(None, pattern="^(active|inactive|suspended)$")


class AgentResponse(BaseModel):
    id: str
    name: str
    description: str
    agent_type: str
    wallet_address: str
    capabilities: list[str]
    a2a_endpoint: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    agents: list[AgentResponse]
