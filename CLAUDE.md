# AgentChains — Claude Code Instructions

## Git Identity
Author must always be: Danda Akhil Reddy <akhilreddydanda3@gmail.com>
NEVER use a placeholder or wrong email. Always verify `git config user.email` matches.

## Git Workflow — Feature Branches + Push After Every Commit

**CRITICAL: NEVER commit directly to master. All work happens on feature branches.**

### Branch naming
- Features: `feat/<name>`
- Fixes: `fix/<name>`
- Chores: `chore/<name>`

### Workflow for every change
1. Create or switch to a feature branch: `git checkout -b feat/<name>`
2. `git add` the changed files
3. `git commit` with a conventional commit message
4. `git push origin <branch>` immediately after each commit
5. When done, merge to master with `--no-ff` to preserve history

Rules:
- One commit per logical change (don't batch multiple changes into one commit)
- Even fixing a typo, updating a comment, or changing one config value = its own commit
- Never skip committing. Every change = one contribution on GitHub.
- **Push after every commit. NEVER batch multiple commits before pushing.**
- The PreToolUse hook will BLOCK edits on master — this is enforced automatically

### WRONG (committing on master — BLOCKED BY HOOK):
```
git checkout master
git add file1 && git commit -m "change 1"  # ← BLOCKED
```

### RIGHT (feature branch, push after every commit):
```
git checkout -b feat/my-feature
git add file1 && git commit -m "feat: add feature" && git push origin feat/my-feature
git add file2 && git commit -m "fix: correct typo" && git push origin feat/my-feature
# When done:
git checkout master && git merge --no-ff feat/my-feature && git push origin master
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

## Code Review — MANDATORY

Before every commit, you MUST review the changes for:
1. **Security**: No hardcoded secrets, API keys, passwords, or tokens in code
2. **Error handling**: All async operations have proper try/except, all API endpoints return appropriate HTTP status codes
3. **Code quality**: No code duplication, proper naming conventions, functions under 50 lines
4. **Python best practices**: Type hints on function signatures, proper async/await usage, SQLAlchemy session handling
5. **TypeScript best practices**: Proper typing, no `any` types, React hooks rules followed
6. **Test impact**: If modifying service logic, corresponding tests must be updated

If you find CRITICAL issues (security vulnerabilities, data leaks, broken error handling), fix them before committing.

To run a full code review at any time: `/agents/code-reviewer`
