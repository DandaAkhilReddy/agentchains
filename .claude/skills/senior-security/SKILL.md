---
name: senior-security
description: Comprehensive security assessment — secret scanning, dependency auditing, auth/authz review, input validation, injection checks, and error leakage detection.
allowed-tools: Read, Bash, Glob, Grep
agent: reviewer
user_invocable: true
context: fork
---

Run a full security assessment on the current project: $ARGUMENTS

## Assessment Steps

### 1. Secret Scanning
Search for hardcoded secrets, tokens, and credentials:
```bash
grep -rn --include='*.py' --include='*.ts' --include='*.js' --include='*.json' --include='*.yaml' --include='*.yml' \
  -E '(password|secret|token|api_key|apikey|auth_token|access_key|private_key)\s*[:=]' . \
  | grep -v node_modules | grep -v __pycache__ | grep -v '.git/'
```
Flag any match that contains a literal value (not env var reference).

### 2. Dependency Audit
Check for known vulnerabilities:
- Python: `pip audit` (if available)
- Node.js: `npm audit` (if package.json exists)
Report CRITICAL and HIGH severity findings.

### 3. Auth/Authz Review
Verify all API endpoints have authentication:
- FastAPI: every router endpoint must have `Depends(get_current_user)` or equivalent
- Express: every route must use auth middleware
- Flag any public endpoint that mutates state (POST/PUT/PATCH/DELETE)

### 4. Input Validation
Check that all POST/PUT/PATCH request bodies use validated schemas:
- Python: Pydantic models on request bodies
- TypeScript: Zod schemas or class-validator on DTOs
- Flag raw `request.body` or `request.json()` without schema validation

### 5. SQL Injection Check
Search for string-formatted SQL:
```bash
grep -rn --include='*.py' -E '(f"|f'\''|\.format\(|%s).*([Ss][Ee][Ll][Ee][Cc][Tt]|[Ii][Nn][Ss][Ee][Rr][Tt]|[Uu][Pp][Dd][Aa][Tt][Ee]|[Dd][Ee][Ll][Ee][Tt][Ee])' .
```
Flag any SQL query built with f-strings, .format(), or % interpolation.

### 6. Error Leakage Check
Verify API error responses don't expose internals:
- No stack traces in HTTP responses
- No raw exception messages sent to clients
- Check for bare `except:` or `catch {}` blocks that swallow errors silently

## Output Format

Group findings by severity:
- **CRITICAL**: Hardcoded secrets, SQL injection, missing auth on state-changing endpoints
- **HIGH**: Missing input validation, dependency CVEs, error leakage
- **MEDIUM**: Broad exception handling, missing rate limiting, permissive CORS
- **LOW**: Missing security headers, verbose logging

Each finding: `[SEVERITY] file:line — description`
