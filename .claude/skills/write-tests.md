---
name: write-tests
description: Generate tests for a module or recent changes
user_invocable: true
---

# /write-tests

Generate comprehensive tests for specified code.

## Instructions

1. Accept a target:
   - File path: write tests for that specific module
   - No argument: write tests for recent uncommitted changes
2. Delegate to the **tester** agent: `/agents/tester`
3. The tester will:
   - Read the target code and existing test files
   - Write tests covering happy path, error cases, and edge cases
   - Follow existing test patterns and use shared fixtures
   - Run the tests to verify they pass
4. Test files go in:
   - Python: `marketplace/tests/test_[module].py`
   - Frontend: co-located `__tests__/[Component].test.tsx` or `frontend/src/__tests__/`
