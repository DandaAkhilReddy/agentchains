---
description: Testing conventions and patterns
globs: ["marketplace/tests/**/*.py", "frontend/src/**/*.test.ts", "frontend/src/**/*.test.tsx"]
---

# Testing Rules

## Python (pytest)

### Configuration
- Async mode: auto (no need for `@pytest.mark.asyncio` decorator in most cases)
- Test path: `marketplace/tests/`
- Run all: `pytest marketplace/tests/ -x -q`
- Run one: `pytest marketplace/tests/test_file.py::test_name -x -v`

### Naming
- Files: `test_<module>.py`
- Functions: `test_<action>_<condition>_<expected_result>`
- Example: `test_create_listing_with_duplicate_slug_raises_conflict`

### Structure
```python
async def test_get_listing_returns_200(async_client, auth_headers):
    # Arrange
    listing = await create_test_listing(async_client, auth_headers)

    # Act
    response = await async_client.get(f"/api/v1/listings/{listing['id']}", headers=auth_headers)

    # Assert
    assert response.status_code == 200
    assert response.json()["id"] == listing["id"]
```

### Fixtures
- Use shared fixtures from `conftest.py`
- `async_client` — httpx AsyncClient with test app
- `auth_headers` — valid auth token headers
- Create factory functions for test data, not fixtures with side effects

## TypeScript (Vitest)

### Configuration
- Config: `frontend/vitest.config.ts`
- Run all: `cd frontend && npx vitest run`
- Run one: `cd frontend && npx vitest run src/__tests__/file.test.ts`

### Naming
- Files: `ComponentName.test.tsx` or `utilName.test.ts`
- Tests: `it("should [expected behavior] when [condition]")`

## Rules
- Never skip tests (`@pytest.mark.skip`) without a comment explaining why
- Test behavior, not implementation
- Mock external services, not internal modules
- Clean up test data — don't rely on test execution order
