# Codex Working Rules

## Branching (always)
- Never work directly on `master`.
- If currently on `master`, create and switch to a new branch named:
  `codex/<short-task>-<yyyymmdd>`.

## Editing style
- Match existing style and patterns.
- Make minimal, surgical edits.
- Do not use placeholder comments such as `// existing code...`.

## Validation
- Run tests and lint before shipping.
- Fix failures before committing.

## Ship process (automatic when task is done)
1) Stage + commit:
- `git add -A`
- `git commit -m "<type>: <summary>"`

2) Push branch:
- `git push -u origin HEAD`

3) Open PR to master and enable auto-merge with squash:
- `gh pr create --fill --base master`
- `gh pr merge --auto --squash --delete-branch`
