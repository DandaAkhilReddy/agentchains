---
name: verify-build
description: Run full build verification (lint, test, build)
user_invocable: true
---

# /verify-build

Run the full build verification pipeline.

## Instructions

Execute all verification steps and report results:

### 1. Python Lint
```bash
ruff check marketplace/ agents/
```

### 2. Python Tests
```bash
pytest marketplace/tests/ -x -q
```

### 3. Frontend Lint
```bash
cd frontend && npm run lint
```

### 4. Frontend Type Check
```bash
cd frontend && npx tsc --noEmit
```

### 5. Frontend Tests
```bash
cd frontend && npx vitest run
```

### 6. Frontend Build
```bash
cd frontend && npm run build
```

## Output
Report each step as PASS or FAIL with details on any failures. If any step fails, stop and report — do not continue to later steps.
