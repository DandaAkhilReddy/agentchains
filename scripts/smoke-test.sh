#!/bin/bash
set -e

BACKEND_URL="${1:-http://localhost:8000}"
FRONTEND_URL="${2:-http://localhost:5173}"
PASS=0
FAIL=0

check() {
  local name="$1"
  local result="$2"
  if [ "$result" = "PASS" ]; then
    echo "  [PASS] $name"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] $name — $result"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== Smoke Test Suite ==="
echo "Backend:  $BACKEND_URL"
echo "Frontend: $FRONTEND_URL"
echo ""

# 1. Backend liveness
STATUS=$(curl -sf "$BACKEND_URL/api/health" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "FAILED")
[ "$STATUS" = "healthy" ] && check "Backend /api/health" "PASS" || check "Backend /api/health" "got: $STATUS"

# 2. Backend readiness
DB_OK=$(curl -sf "$BACKEND_URL/api/health/ready" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('database',''))" 2>/dev/null || echo "FAILED")
[ "$DB_OK" = "True" ] && check "Backend /api/health/ready" "PASS" || check "Backend /api/health/ready" "database: $DB_OK"

# 3. EMI calculator (public endpoint)
EMI=$(curl -sf -X POST "$BACKEND_URL/api/emi/calculate" \
  -H "Content-Type: application/json" \
  -d '{"principal":1000000,"annual_rate":8.5,"tenure_months":240}' 2>/dev/null | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('emi',0) > 0 else 'BAD')" 2>/dev/null || echo "FAILED")
[ "$EMI" = "OK" ] && check "EMI calculator" "PASS" || check "EMI calculator" "got: $EMI"

# 4. Frontend serves HTML
FE_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$FRONTEND_URL/" 2>/dev/null)
[ "$FE_STATUS" = "200" ] && check "Frontend serves HTML" "PASS" || check "Frontend serves HTML" "HTTP $FE_STATUS"

# 5. Auth endpoint returns 400/401 (not connection refused)
AUTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BACKEND_URL/api/auth/verify-token" \
  -H "Content-Type: application/json" -d '{}' 2>/dev/null)
[[ "$AUTH_STATUS" =~ ^(400|401|422)$ ]] && check "Auth endpoint reachable" "PASS" || check "Auth endpoint reachable" "HTTP $AUTH_STATUS"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
