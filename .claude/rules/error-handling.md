---
description: Error handling patterns for backend services and API
globs: ["marketplace/api/**/*.py", "marketplace/services/**/*.py"]
---

# Error Handling Rules

## Domain Exceptions
Use domain-specific exceptions from `marketplace/core/exceptions.py`. Never raise generic `Exception` or `ValueError` from service code.

## API Layer (`marketplace/api/`)
- Catch domain exceptions and map to HTTP status codes
- 400: Validation errors, bad input
- 401: Authentication required
- 403: Authorization denied (use `AuthorizationError`)
- 404: Resource not found
- 409: Conflict (duplicate resources)
- 500: Unexpected errors (log the traceback)

## Service Layer (`marketplace/services/`)
- Raise domain exceptions, not HTTP exceptions
- Wrap external API calls in try/except
- Always clean up resources (DB sessions, file handles) in finally blocks
- Log errors with context (user ID, resource ID, operation)

## Async Error Handling
```python
async def create_listing(self, data: CreateListingSchema) -> Listing:
    try:
        listing = Listing(**data.model_dump())
        self.session.add(listing)
        await self.session.commit()
        return listing
    except IntegrityError:
        await self.session.rollback()
        raise DuplicateResourceError(f"Listing with slug '{data.slug}' already exists")
```

## Rules
- Never silently swallow exceptions (empty `except: pass`)
- Always rollback the session on database errors
- Include relevant context in error messages
- Log at appropriate levels: ERROR for failures, WARNING for recoverable issues
