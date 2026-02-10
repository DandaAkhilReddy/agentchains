from pydantic import BaseModel


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int


class ErrorResponse(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: str
    version: str
    agents_count: int
    listings_count: int
    transactions_count: int
