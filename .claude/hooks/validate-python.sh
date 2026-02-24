#!/usr/bin/env bash
# Validate staged Python files with ruff before commit.
# Called by hooks.json as a PreToolUse command hook.

set -euo pipefail

# Get staged Python files
STAGED_PY=$(git diff --cached --name-only --diff-filter=ACM -- '*.py' 2>/dev/null || true)

if [ -z "$STAGED_PY" ]; then
  echo "[validate-python] No staged Python files — skipping."
  exit 0
fi

echo "[validate-python] Checking staged Python files with ruff..."

# Run ruff check on staged files
if command -v ruff &>/dev/null; then
  # shellcheck disable=SC2086
  ruff check --no-fix $STAGED_PY
  echo "[validate-python] All checks passed."
else
  echo "[validate-python] ruff not found — skipping lint check."
fi
