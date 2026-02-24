---
name: implement-task
description: Implement a planned task or feature
user_invocable: true
---

# /implement-task

Implement a specific task from a plan or a standalone code change.

## Instructions

1. Accept a task description or reference to a plan in `.planning/plans/`
2. Delegate to the **implementer** agent: `/agents/implementer`
3. The implementer will:
   - Read relevant existing code to understand patterns
   - Write the implementation following project conventions
   - Review changes for security, error handling, and types
   - Run relevant tests to verify the change works
4. Each logical change gets its own atomic commit
5. Push after each commit per project workflow
