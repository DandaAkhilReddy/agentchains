# AgentChains — Claude Code Instructions

## Git Identity
Author must always be: Danda Akhil Reddy <akhilreddydanda3@gmail.com>
NEVER use a placeholder or wrong email. Always verify `git config user.email` matches.

## Git Workflow — Commit AND PUSH Everything

**CRITICAL: `git push origin master` MUST run immediately after EVERY `git commit`. NEVER batch pushes.**

After EVERY code change — no matter how small (even a single word, line, or letter) — always run all 3 steps together:
1. `git add` the changed files
2. `git commit` with a descriptive message
3. **`git push origin master`** ← THIS IS MANDATORY AFTER EVERY SINGLE COMMIT

Rules:
- One commit per logical change (don't batch multiple changes into one commit)
- Even fixing a typo, updating a comment, or changing one config value = its own commit
- Never skip committing. Every change = one contribution on GitHub.
- This applies to every change — no exceptions.
- **NEVER run multiple `git commit` commands before pushing. Each commit gets its own push.**

### WRONG (batched push — DO NOT DO THIS):
```
git add file1 && git commit -m "change 1"
git add file2 && git commit -m "change 2"
git add file3 && git commit -m "change 3"
git push origin master   # ← BAD: 3 commits pushed at once
```

### RIGHT (push after every commit):
```
git add file1 && git commit -m "change 1" && git push origin master
git add file2 && git commit -m "change 2" && git push origin master
git add file3 && git commit -m "change 3" && git push origin master
```

## Commits — CRITICAL RULES
- NEVER add Co-Authored-By trailers to any commit message
- Use conventional commits: feat/fix/chore/docs/refactor/test
- Keep commits small and atomic — one logical change per commit
- Always use regular merges to master (never squash or rebase merges)
- Never force-push to master

## Branch Strategy
- Feature work on feature branches, merged (not squashed) to master
- Merge feature branches to master at least weekly so commits count on the contribution graph
