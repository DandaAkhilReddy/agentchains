---
description: Git commit message conventions
globs: ["**/*"]
---

# Commit Conventions

## Format
```
type(scope): description
```

## Types
- `feat` — New feature or capability
- `fix` — Bug fix
- `refactor` — Code change that neither fixes a bug nor adds a feature
- `test` — Adding or updating tests
- `docs` — Documentation changes
- `chore` — Maintenance tasks, config changes, dependencies
- `perf` — Performance improvement

## Scope (optional)
- Module or area affected: `api`, `services`, `models`, `frontend`, `agents`, `.claude`, `.planning`

## Rules
- Subject line: imperative mood, lowercase, no period, under 72 chars
- One logical change per commit
- Push immediately after each commit
- Never add Co-Authored-By trailers
- Author: Danda Akhil Reddy <akhilreddydanda3@gmail.com>

## Examples
```
feat(api): add listing search endpoint
fix(services): handle expired token in auth middleware
test(services): add unit tests for transaction rollback
refactor(models): extract base model mixin for timestamps
docs(.claude): add planner agent definition
chore: update ruff to v0.5.0
```
