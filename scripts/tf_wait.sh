#!/usr/bin/env bash
# Wait until Token Factory's Gemma answers a tiny JSON request (it returned 503 "no available workers" on 16 Oct).
cd "$(dirname "$0")/.."
set -a; source .env; set +a
for i in $(seq 1 ${1:-180}); do
  code=$(curl -s -m 60 -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $AMD_TF_API_KEY" \
    -H "Content-Type: application/json" "$AMD_TF_BASE_URL/chat/completions" \
    -d '{"model":"Gemma-4-31B-IT","messages":[{"role":"user","content":"Reply {\"ok\":true}"}],"max_tokens":10,"response_format":{"type":"json_object"}}')
  echo "$(date -u +%FT%TZ) $code"
  [ "$code" = "200" ] && exit 0
  sleep 120
done
exit 1
