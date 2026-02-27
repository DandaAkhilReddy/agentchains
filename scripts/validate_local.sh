#!/usr/bin/env bash
set -euo pipefail

# ── Local Docker Compose Validation Script ───────────────────
# Starts the full stack, runs smoke tests, then tears down.
# Usage: ./scripts/validate_local.sh

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

APP_URL="http://localhost:8080"
MAX_WAIT=120  # seconds to wait for app to become healthy
POLL_INTERVAL=5

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[FAIL]${NC} $*"; }

cleanup() {
    log_info "Tearing down containers..."
    docker compose -f docker-compose.yml down --volumes --remove-orphans 2>/dev/null || true
}
trap cleanup EXIT

# ── Step 1: Start services ──────────────────────────────────
log_info "Starting Docker Compose stack (production mode)..."
docker compose -f docker-compose.yml up -d --build

# ── Step 2: Wait for health ─────────────────────────────────
log_info "Waiting for app to become healthy (max ${MAX_WAIT}s)..."
elapsed=0
healthy=false

while [ $elapsed -lt $MAX_WAIT ]; do
    status=$(curl -s -o /dev/null -w "%{http_code}" "${APP_URL}/api/v1/health" 2>/dev/null || echo "000")
    if [ "$status" = "200" ]; then
        healthy=true
        break
    fi
    sleep $POLL_INTERVAL
    elapsed=$((elapsed + POLL_INTERVAL))
    echo "  ... waiting (${elapsed}s, last status: ${status})"
done

if [ "$healthy" = false ]; then
    log_error "App did not become healthy within ${MAX_WAIT}s"
    log_warn "Container logs:"
    docker compose -f docker-compose.yml logs --tail=50 app
    exit 1
fi
log_info "App is healthy after ${elapsed}s"

# ── Step 3: Smoke tests ─────────────────────────────────────
PASS=0
FAIL=0

smoke_test() {
    local name="$1"
    local method="$2"
    local path="$3"
    local expected_status="$4"
    local body="${5:-}"

    if [ -n "$body" ]; then
        actual=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" \
            -H "Content-Type: application/json" \
            -d "$body" \
            "${APP_URL}${path}" 2>/dev/null || echo "000")
    else
        actual=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" \
            "${APP_URL}${path}" 2>/dev/null || echo "000")
    fi

    if [ "$actual" = "$expected_status" ]; then
        log_info "PASS: ${name} (${actual})"
        PASS=$((PASS + 1))
    else
        log_error "FAIL: ${name} (expected ${expected_status}, got ${actual})"
        FAIL=$((FAIL + 1))
    fi
}

log_info "Running smoke tests..."

# Core health
smoke_test "Health check"              GET  "/api/v1/health"           200
smoke_test "Readiness check"           GET  "/api/v1/health"           200

# API discovery
smoke_test "Agents list"               GET  "/api/v1/registry"         200
smoke_test "Listings list"             GET  "/api/v1/listings"         200
smoke_test "Catalog search"            GET  "/api/v1/catalog/search"   200

# V2 endpoints
smoke_test "V2 analytics"              GET  "/api/v2/analytics/overview" 200

# V5 judge endpoint (requires auth, should return 401)
smoke_test "Judge evaluate (no auth)"  POST "/api/v5/judge/evaluate"   401

# V5 judge list (requires auth, should return 401)
smoke_test "Judge list (no auth)"      POST "/api/v5/judge/evaluations" 401

# V5 chains
smoke_test "Chains list"               GET  "/api/v5/chains/templates" 200

# ── Step 4: Report ──────────────────────────────────────────
echo ""
log_info "═══════════════════════════════════════"
log_info "Smoke Test Results: ${PASS} passed, ${FAIL} failed"
log_info "═══════════════════════════════════════"

if [ $FAIL -gt 0 ]; then
    log_error "Some smoke tests failed!"
    exit 1
fi

log_info "All smoke tests passed!"
exit 0
