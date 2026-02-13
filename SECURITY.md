# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.4.x   | :white_check_mark: |
| 0.3.x   | :warning: Critical fixes only |
| < 0.3   | :x: No longer supported |

## Reporting Vulnerabilities

We take security seriously. If you discover a vulnerability, please report it responsibly.

**Email:** security@agentchains.dev

### What to Include

- A clear description of the vulnerability
- Steps to reproduce the issue
- Affected version(s) and component(s)
- Potential impact assessment
- Any suggested fix or mitigation (optional but appreciated)

### Expected Response Time

- **Acknowledgement:** Within 48 hours of receipt
- **Initial assessment:** Within 5 business days
- **Resolution target:** Within 30 days for critical issues, 90 days for non-critical

You will receive updates at each stage. If you have not received an acknowledgement within 48 hours, please follow up to confirm we received your report.

## Responsible Disclosure Policy

- Please give us reasonable time to investigate and address the issue before public disclosure.
- We ask that you do not exploit the vulnerability beyond what is necessary to demonstrate it.
- Do not access, modify, or delete data belonging to other users.
- We will credit reporters in our release notes (unless you prefer to remain anonymous).
- We will not pursue legal action against researchers who follow this policy in good faith.

## Security Measures in Place

### Authentication

- **JWT authentication** using HS256 signing algorithm
- Tokens are validated on every protected endpoint
- Token expiration is enforced server-side

### Rate Limiting

- **Sliding window** rate limiting algorithm
- **Per-IP** tracking to prevent abuse from individual sources
- Configurable thresholds per endpoint category

### Security Headers

The application sets the following HTTP security headers:

- **Content-Security-Policy (CSP):** Restricts resource loading to trusted origins
- **Strict-Transport-Security (HSTS):** Enforces HTTPS connections
- **X-Frame-Options:** Prevents clickjacking via `DENY`
- **X-Content-Type-Options:** Prevents MIME-type sniffing via `nosniff`
- **Referrer-Policy:** Controls referrer information leakage
- **Permissions-Policy:** Restricts browser feature access

### Ledger Integrity

- **SHA-256 hash chain** ensures tamper-evident ledger records
- Each entry references the hash of the previous entry, creating an immutable audit trail
- Any modification to historical records breaks the chain and is immediately detectable

### Input Validation

- **Pydantic schemas** enforce strict type checking and constraints on all API inputs
- Request payloads are validated before reaching business logic
- Malformed or unexpected data is rejected with descriptive error responses

### CORS Configuration

- Cross-Origin Resource Sharing is configured to restrict which origins can interact with the API
- Allowed methods and headers are explicitly defined

## Known Limitations

### In-Memory Rate Limiter

The current rate limiter stores counters in application memory. This means:

- Rate limit state is **not shared** across multiple server instances
- State is **lost on restart**
- For production deployments with multiple workers or replicas, use a distributed store such as Redis

### SQLite in Development

The default development configuration uses SQLite for simplicity. SQLite is **not recommended for production** because:

- It does not handle concurrent writes well under load
- It lacks some features needed for robust production operation
- **Use PostgreSQL** for any production or staging deployment

### CORS Origins

The default `CORS_ORIGINS` configuration is permissive for local development. In production:

- Set `CORS_ORIGINS` to an explicit allowlist of your frontend domain(s)
- Never use wildcard (`*`) origins in production

## Security Best Practices for Deployment

1. **Use HTTPS everywhere.** Terminate TLS at your reverse proxy (e.g., Nginx, Caddy) or load balancer. Never expose the application over plain HTTP in production.

2. **Set strong secrets.** Generate a cryptographically random `JWT_SECRET_KEY` (minimum 256 bits). Never reuse secrets across environments. Store secrets in environment variables or a secrets manager -- never commit them to source control.

3. **Use PostgreSQL in production.** Replace SQLite with PostgreSQL and configure connection pooling. Enable SSL for database connections.

4. **Configure CORS strictly.** Set `CORS_ORIGINS` to only your production frontend domain(s).

5. **Deploy behind a reverse proxy.** Use Nginx, Caddy, or a cloud load balancer to handle TLS termination, request buffering, and an additional layer of rate limiting.

6. **Use a distributed rate limiter.** Replace the in-memory rate limiter with a Redis-backed implementation if running multiple server instances.

7. **Enable logging and monitoring.** Collect application logs centrally. Monitor for unusual patterns such as repeated authentication failures or rate limit hits.

8. **Keep dependencies updated.** Regularly run `pip audit` and `npm audit` to check for known vulnerabilities in dependencies. Pin dependency versions and review updates before applying them.

9. **Restrict network access.** Use firewalls and security groups to limit which IPs and ports can reach your database and backend services. The database should never be publicly accessible.

10. **Run with least privilege.** Do not run the application as root. Use a dedicated service account with minimal filesystem and network permissions.
