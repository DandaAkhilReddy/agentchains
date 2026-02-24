---
name: review-code
description: Perform a comprehensive PR-style code review
user_invocable: true
---

# /review-code

Run a thorough code review on recent changes.

## Instructions

1. Determine the scope of review:
   - If an argument is provided (file path, commit range), review that scope
   - Otherwise, review all uncommitted changes (`git diff`) and staged changes (`git diff --staged`)
2. Delegate to the **reviewer** agent: `/agents/reviewer`
3. The reviewer will:
   - Analyze all changes for correctness, security, performance, and conventions
   - Read full files for context (not just diffs)
   - Cross-reference with related models, schemas, and tests
   - Produce a structured review with severity-rated findings
4. Present the review findings to the user
