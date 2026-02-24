---
description: Python code style conventions for marketplace and agents
globs: ["marketplace/**/*.py", "agents/**/*.py"]
---

# Python Style Rules

## Formatting
- Line length: 100 characters (matches `pyproject.toml` ruff config)
- Formatter: ruff format
- Target: Python 3.11+

## Naming
- Functions and variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private members: `_leading_underscore`
- File names: `snake_case.py`

## Type Hints
- Required on all function signatures (parameters and return types)
- Use `|` union syntax over `Optional[]` (Python 3.11+)
- Use `list[T]`, `dict[K, V]` over `List[T]`, `Dict[K, V]`
- Complex types: define type aliases at module level

## Imports
- Standard library first, then third-party, then local
- Use absolute imports: `from marketplace.services.listing_service import ListingService`
- No wildcard imports (`from module import *`)

## Async
- All I/O-bound functions must be `async def`
- Never use `time.sleep()` — use `asyncio.sleep()`
- Never call sync DB operations in async context

## Functions
- Keep under 50 lines
- Single responsibility
- Docstrings only for non-obvious public APIs
