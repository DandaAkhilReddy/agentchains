from pydantic import BaseModel


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int


class ErrorResponse(BaseModel):
    detail: str


class CacheStats(BaseModel):
    listings: dict
    content: dict
    agents: dict


class HealthResponse(BaseModel):
    status: str
    version: str
    agents_count: int
    listings_count: int
    transactions_count: int
    cache_stats: CacheStats | None = None
