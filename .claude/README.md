# `.claude/` Directory

Claude Code configuration for the AgentChains project.

## Structure

```
.claude/
  settings.json         # Shared team permissions (committed)
  settings.local.json   # Personal permissions (gitignored)
  hooks.json            # Pre-commit and session hooks
  agents/               # Agent definitions
    code-reviewer.md    # Quick pre-commit review (/review-code)
    planner.md          # Feature planning (/agents/planner)
    implementer.md      # Code implementation (/agents/implementer)
    reviewer.md         # Deep PR-style review (/agents/reviewer)
    tester.md           # Test generation (/agents/tester)
    debugger.md         # Bug diagnosis (/agents/debugger)
  skills/               # Slash command skills
    plan-feature.md     # /plan-feature
    implement-task.md   # /implement-task
    review-code.md      # /review-code
    write-tests.md      # /write-tests
    verify-build.md     # /verify-build
  rules/                # Context-triggered rules (activate by file glob)
    api-design.md       # REST API conventions (project-specific)
    agent-patterns.md   # AI agent patterns (project-specific)
    # Python style, commit conventions, error handling, and testing
    # rules are defined globally in ~/.claude/rules/
  hooks/                # Hook scripts
    validate-python.sh  # Ruff lint check on staged Python files
```

## Quick Reference

| Command | Purpose |
|---------|---------|
| `/plan-feature` | Design a feature implementation plan |
| `/implement-task` | Implement a planned task |
| `/review-code` | Comprehensive code review |
| `/write-tests` | Generate tests for a module |
| `/verify-build` | Run full lint + test + build pipeline |
| `/review-code` | Quick pre-commit review |

## How Rules Work

Rules in `.claude/rules/` activate automatically when editing files matching their `globs` pattern. For example, `python-style.md` activates when editing `marketplace/**/*.py` files.

## Adding New Agents/Skills/Rules

- **Agent**: Create `.claude/agents/<name>.md` with role, process, and output format
- **Skill**: Create `.claude/skills/<name>.md` with frontmatter (`name`, `description`, `user_invocable: true`)
- **Rule**: Create `.claude/rules/<name>.md` with frontmatter (`description`, `globs`)
