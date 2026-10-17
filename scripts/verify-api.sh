#!/bin/sh
set -eu
BASE=${1:-http://localhost:8080}
BODY='{"product_id":1,"sku":"ABC-123","manufacturer":"Acme","category_id":1,"weight":0,"some_other_id":1}'
run() {
 label=$1; expected=$2; shift 2
 printf '\n%s (expected %s)\n' "$label" "$expected"
 output=$(mktemp)
 code=$(curl -sS -o "$output" -w '%{http_code}' "$@")
 printf 'HTTP %s\n' "$code"
 cat "$output"
 printf '\n'
 if [ "$expected" = 204 ] && [ -s "$output" ]; then echo 'FAIL: 204 body must be empty'; exit 1; fi
 rm -f "$output"
 [ "$code" = "$expected" ] || { echo 'FAIL'; exit 1; }
}
run 'GET existing' 200 "$BASE/products/1"
run 'GET missing' 404 "$BASE/products/1001"
run 'GET controlled fault' 500 -H 'X-Fault-Inject: 500' "$BASE/products/1"
run 'POST valid, zero weight' 204 -H 'Content-Type: application/json' -d "$BODY" "$BASE/products/1/details"
run 'POST invalid JSON' 400 -H 'Content-Type: application/json' -d '{' "$BASE/products/1/details"
run 'POST missing product' 404 -H 'Content-Type: application/json' -d '{"product_id":1001,"sku":"ABC","manufacturer":"Acme","category_id":1,"weight":0,"some_other_id":1}' "$BASE/products/1001/details"
run 'POST controlled fault' 500 -H 'X-Fault-Inject: 500' -H 'Content-Type: application/json' -d "$BODY" "$BASE/products/1/details"
run 'GET confirms update' 200 "$BASE/products/1"
printf '\nPASS: all seven endpoint/status combinations.\n'
