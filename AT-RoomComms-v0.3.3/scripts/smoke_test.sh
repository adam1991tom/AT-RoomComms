#!/usr/bin/env bash
# AT RoomComms — API smoke test for the v0.4.0 operator/access-control work.
#
# Verifies: admin login, room/event/operator setup, operator room-login,
# room-scoped access control, emergency reply threading, direct messages,
# and (optionally, see RUN_CUTOFF_TEST below) the daily sign-out cutoff.
#
# Usage:
#   ./smoke_test.sh
#   BASE_URL=http://10.0.0.2:5070 ADMIN_USER=admin ADMIN_PASS=adminpass123 ./smoke_test.sh
#
# Requires: curl, jq
#
# WARNING: with RUN_CUTOFF_TEST=1 this test forces the daily sign-out cutoff to
# fire within ~90 seconds, which logs EVERYONE off the target server — every
# Control Centre login AND every operator room session. Never run that against
# a server anyone is actively using. It is off by default.

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:5070}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-adminpass123}"
RUN_CUTOFF_TEST="${RUN_CUTOFF_TEST:-0}"
SUFFIX="$(date +%s)"
CLEANUP=1

pass() { echo "  OK  - $1"; }
fail() { echo "  FAIL - $1"; exit 1; }
expect_code() { # expect_code <expected> <actual> <label>
  if [ "$2" = "$1" ]; then pass "$3 (HTTP $2)"; else fail "$3 (expected HTTP $1, got $2)"; fi
}

command -v jq >/dev/null || { echo "jq is required"; exit 1; }

echo "== AT RoomComms smoke test against $BASE_URL =="

echo "-- health --"
HEALTH=$(curl -sf "$BASE_URL/api/health")
echo "$HEALTH" | jq .

echo "-- admin login --"
LOGIN=$(curl -sf -X POST "$BASE_URL/api/auth/login" -H "Content-Type: application/json" \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}") || fail "admin login (check ADMIN_USER/ADMIN_PASS)"
ADMIN_TOKEN=$(echo "$LOGIN" | jq -r .token)
pass "admin login"

cleanup() {
  [ "$CLEANUP" = "1" ] || return 0
  echo "-- cleanup --"
  [ -n "${RID:-}" ] && curl -s -X DELETE "$BASE_URL/api/rooms/$RID" -H "Authorization: Bearer $ADMIN_TOKEN" >/dev/null || true
  [ -n "${RID2:-}" ] && curl -s -X DELETE "$BASE_URL/api/rooms/$RID2" -H "Authorization: Bearer $ADMIN_TOKEN" >/dev/null || true
  [ -n "${EID:-}" ] && curl -s -X DELETE "$BASE_URL/api/events/$EID" -H "Authorization: Bearer $ADMIN_TOKEN" >/dev/null || true
  [ -n "${OP1ID:-}" ] && curl -s -X DELETE "$BASE_URL/api/operators/$OP1ID" -H "Authorization: Bearer $ADMIN_TOKEN" >/dev/null || true
  [ -n "${OP2ID:-}" ] && curl -s -X DELETE "$BASE_URL/api/operators/$OP2ID" -H "Authorization: Bearer $ADMIN_TOKEN" >/dev/null || true
  echo "  removed smoke-test room/event/operator records"
}
trap cleanup EXIT

echo "-- create test room/event/operators (smoke-$SUFFIX) --"
RID=$(curl -sf -X POST "$BASE_URL/api/rooms" -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\":\"Smoke Room A $SUFFIX\",\"short_name\":\"A\"}" | jq -r .id)
RID2=$(curl -sf -X POST "$BASE_URL/api/rooms" -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\":\"Smoke Room B $SUFFIX\",\"short_name\":\"B\"}" | jq -r .id)
EID=$(curl -sf -X POST "$BASE_URL/api/events" -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\":\"Smoke Event $SUFFIX\"}" | jq -r .id)
curl -sf -X POST "$BASE_URL/api/events/$EID/rooms/$RID" -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"operator_name":"SmokeOp1"}' >/dev/null
curl -sf -X POST "$BASE_URL/api/events/$EID/rooms/$RID2" -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"operator_name":"SmokeOp2"}' >/dev/null
OP1ID=$(curl -sf -X POST "$BASE_URL/api/operators" -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d "{\"name\":\"SmokeOp1 $SUFFIX\"}" | jq -r .id)
OP2ID=$(curl -sf -X POST "$BASE_URL/api/operators" -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d "{\"name\":\"SmokeOp2 $SUFFIX\"}" | jq -r .id)
pass "created room A=$RID room B=$RID2 event=$EID operators=$OP1ID,$OP2ID"

echo "-- operator logins --"
OP1_TOKEN=$(curl -sf -X POST "$BASE_URL/api/operator/login" -H "Content-Type: application/json" \
  -d "{\"operator_id\":$OP1ID,\"event_id\":$EID,\"room_id\":$RID,\"device_role\":\"main\"}" | jq -r .token)
OP2_TOKEN=$(curl -sf -X POST "$BASE_URL/api/operator/login" -H "Content-Type: application/json" \
  -d "{\"operator_id\":$OP2ID,\"event_id\":$EID,\"room_id\":$RID2,\"device_role\":\"backup\"}" | jq -r .token)
pass "operator 1 -> room A, operator 2 -> room B"

echo "-- room-scoped access control --"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/api/messages" -H "Authorization: Bearer $OP1_TOKEN" -H "Content-Type: application/json" \
  -d "{\"scope\":\"room\",\"scope_id\":$RID,\"body\":\"hello from op1\",\"priority\":\"normal\"}")
expect_code 200 "$CODE" "operator can post to own room"
CODE=$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/api/messages?scope=room&scope_id=$RID2" -H "Authorization: Bearer $OP1_TOKEN")
expect_code 403 "$CODE" "operator blocked from reading other room"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/api/messages" -H "Authorization: Bearer $OP1_TOKEN" -H "Content-Type: application/json" \
  -d "{\"scope\":\"room\",\"scope_id\":$RID2,\"body\":\"sneaky\",\"priority\":\"normal\"}")
expect_code 403 "$CODE" "operator blocked from posting to other room"
CODE=$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/api/messages?scope=venue" -H "Authorization: Bearer $OP1_TOKEN")
expect_code 403 "$CODE" "operator blocked from venue feed"
CODE=$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/api/messages?scope=room&scope_id=$RID" -H "Authorization: Bearer $ADMIN_TOKEN")
expect_code 200 "$CODE" "admin can still read any room"

echo "-- emergency reply threading --"
EMERG_ID=$(curl -sf -X POST "$BASE_URL/api/messages" -H "Authorization: Bearer $OP1_TOKEN" -H "Content-Type: application/json" \
  -d "{\"scope\":\"room\",\"scope_id\":$RID,\"body\":\"smoke test emergency\",\"priority\":\"emergency\"}" | jq -r .id)
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/api/messages" -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d "{\"scope\":\"emergency_thread\",\"scope_id\":$EMERG_ID,\"body\":\"on it\",\"priority\":\"normal\"}")
expect_code 200 "$CODE" "admin can reply privately to emergency"
CODE=$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/api/messages?scope=emergency_thread&scope_id=$EMERG_ID" -H "Authorization: Bearer $OP1_TOKEN")
expect_code 200 "$CODE" "reporter can read their own emergency thread"
CODE=$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/api/messages?scope=emergency_thread&scope_id=$EMERG_ID" -H "Authorization: Bearer $OP2_TOKEN")
expect_code 403 "$CODE" "other operator blocked from emergency thread"

echo "-- direct messages --"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/api/dm" -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d "{\"to_kind\":\"operator\",\"to_id\":$OP1ID,\"body\":\"smoke dm\"}")
expect_code 200 "$CODE" "admin can DM an operator"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/api/dm" -H "Authorization: Bearer $OP2_TOKEN" -H "Content-Type: application/json" \
  -d "{\"to_kind\":\"operator\",\"to_id\":$OP1ID,\"body\":\"sneaky dm\"}")
expect_code 403 "$CODE" "operator blocked from DMing another operator"

if [ "$RUN_CUTOFF_TEST" = "1" ]; then
  echo "-- daily sign-out cutoff (DISRUPTIVE: logs off every session on this server) --"
  FUTURE=$(date -u -d "+70 seconds" +%H:%M)
  curl -sf -X PATCH "$BASE_URL/api/settings" -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
    -d "{\"daily_logoff_utc\":\"$FUTURE\"}" >/dev/null
  echo "  cutoff set to $FUTURE UTC, waiting..."
  TARGET_H=$(date -u -d "+80 seconds" +%H)
  TARGET_M=$(date -u -d "+80 seconds" +%M)
  TARGET_S=$(date -u -d "+80 seconds" +%S)
  until [ "$(date -u +%H%M%S)" -ge "$TARGET_H$TARGET_M$TARGET_S" ]; do sleep 3; done
  CODE=$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/api/auth/me" -H "Authorization: Bearer $ADMIN_TOKEN")
  expect_code 401 "$CODE" "admin token expired after cutoff"
  CODE=$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/api/auth/me" -H "Authorization: Bearer $OP1_TOKEN")
  expect_code 401 "$CODE" "operator token expired after cutoff"
  echo "  re-authenticating to finish cleanup..."
  ADMIN_TOKEN=$(curl -sf -X POST "$BASE_URL/api/auth/login" -H "Content-Type: application/json" \
    -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}" | jq -r .token)
  curl -sf -X PATCH "$BASE_URL/api/settings" -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
    -d '{"daily_logoff_utc":"03:00"}' >/dev/null
  echo "  cutoff setting restored to 03:00"
else
  echo "-- daily sign-out cutoff test SKIPPED (set RUN_CUTOFF_TEST=1 to run it; logs off EVERYONE on the target server) --"
fi

echo
echo "All checks passed."
