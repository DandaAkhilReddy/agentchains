---
name: plan-feature
description: Design an implementation plan for a new feature
user_invocable: true
---

# /plan-feature

Create a detailed implementation plan for a feature request.

## Instructions

1. Ask the user to describe the feature (or use the argument provided)
2. Delegate to the **planner** agent: `/agents/planner`
3. The planner will:
   - Explore the codebase to understand existing patterns
   - Identify all files to create, modify, or delete
   - Break the work into atomic, committable tasks
   - Flag risks and testing requirements
4. Save the plan to `.planning/plans/[feature-name].md`
5. Present the plan for user approval before any implementation begins
