from datetime import datetime

from pydantic import BaseModel


class ReputationResponse(BaseModel):
    agent_id: str
    agent_name: str = ""
    total_transactions: int
    successful_deliveries: int
    failed_deliveries: int
    verified_count: int
    verification_failures: int
    avg_response_ms: float | None = None
    total_volume_usdc: float
    composite_score: float
    last_calculated_at: datetime

    model_config = {"from_attributes": True}


class LeaderboardEntry(BaseModel):
    rank: int
    agent_id: str
    agent_name: str
    composite_score: float
    total_transactions: int
    total_volume_usdc: float


class LeaderboardResponse(BaseModel):
    entries: list[LeaderboardEntry]
