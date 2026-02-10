from datetime import datetime

from pydantic import BaseModel, Field


class AgentRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    agent_type: str = Field(..., pattern="^(seller|buyer|both)$")
    public_key: str = Field(..., min_length=10)
    wallet_address: str = ""
    capabilities: list[str] = []
    a2a_endpoint: str = ""


class AgentRegisterResponse(BaseModel):
    id: str
    name: str
    jwt_token: str
    agent_card_url: str
    created_at: datetime


class AgentUpdateRequest(BaseModel):
    description: str | None = None
    wallet_address: str | None = None
    capabilities: list[str] | None = None
    a2a_endpoint: str | None = None
    status: str | None = None


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
