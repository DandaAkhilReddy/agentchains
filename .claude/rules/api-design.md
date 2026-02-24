---
description: REST API design conventions for FastAPI endpoints
globs: ["marketplace/api/**/*.py", "marketplace/schemas/**/*.py"]
---

# API Design Rules

## URL Conventions
- Prefix: `/api/v1/`
- Plural nouns for resources: `/api/v1/listings`, `/api/v1/agents`
- Nested resources: `/api/v1/listings/{listing_id}/reviews`
- Use kebab-case for multi-word paths: `/api/v1/agent-chains`

## HTTP Methods
- GET: Read (never mutate state)
- POST: Create new resources
- PUT: Full update (replace entire resource)
- PATCH: Partial update
- DELETE: Remove resource

## Response Shapes
- Single resource: `{ "id": ..., "name": ..., ... }`
- Collection: `{ "items": [...], "total": N, "page": N, "per_page": N }`
- Error: `{ "detail": "Human-readable message" }`

## Pydantic Schemas
- Request schemas: `Create[Resource]Schema`, `Update[Resource]Schema`
- Response schemas: `[Resource]Response`
- Use `model_dump()` (Pydantic v2), not `.dict()`
- Define in `marketplace/schemas/`

## FastAPI Patterns
```python
@router.get("/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: int,
    session: AsyncSession = Depends(get_session),
) -> ListingResponse:
    ...
```

## Rules
- Always specify `response_model` on route decorators
- Use dependency injection for sessions, auth, and config
- Paginate all collection endpoints (default: 20 items)
- Return 201 for successful POST, 204 for successful DELETE
- Include `Location` header on 201 responses
