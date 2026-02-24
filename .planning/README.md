# Planning Directory

This directory contains planning artifacts for the AgentChains project.

## Structure

```
.planning/
  README.md             # This file
  templates/            # Reusable plan and decision templates
    feature-plan.md     # Template for feature implementation plans
    adr.md              # Template for Architecture Decision Records
  decisions/            # Completed ADRs
  plans/                # Active feature plans (gitignored)
```

## Usage

### Feature Plans
Use `/plan-feature` to generate a new feature plan. Plans are saved to `.planning/plans/` and are gitignored (ephemeral working documents).

### Architecture Decision Records (ADRs)
For significant architectural decisions, create an ADR in `.planning/decisions/` using the template. ADRs are committed to the repo as permanent records.

## Conventions
- Plans are temporary working documents — do not commit them
- ADRs are permanent records — always commit them
- Number ADRs sequentially: `001-decision-title.md`, `002-next-decision.md`
