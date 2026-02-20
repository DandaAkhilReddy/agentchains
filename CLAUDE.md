# AgentChains — Claude Code Instructions

## Git Identity
Author must always be: Danda Akhil Reddy <akhilreddydanda3@gmail.com>
NEVER use a placeholder or wrong email. Always verify `git config user.email` matches.

## Git Workflow — Commit Everything
After EVERY code change — no matter how small (even a single word, line, or letter) — always:
1. `git add` the changed files
2. `git commit` with a descriptive message
3. `git push origin master`

Rules:
- One commit per logical change (don't batch multiple changes into one commit)
- Even fixing a typo, updating a comment, or changing one config value = its own commit
- Never skip committing. Every change = one contribution on GitHub.
- This applies to every change — no exceptions.

## Commits — CRITICAL RULES
- NEVER add Co-Authored-By trailers to any commit message
- Use conventional commits: feat/fix/chore/docs/refactor/test
- Keep commits small and atomic — one logical change per commit
- Always use regular merges to master (never squash or rebase merges)
- Never force-push to master

## Branch Strategy
- Feature work on feature branches, merged (not squashed) to master
- Merge feature branches to master at least weekly so commits count on the contribution graph
