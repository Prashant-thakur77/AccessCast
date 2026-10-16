#!/usr/bin/env bash
# One GPU session on the MI300X droplet, in phases, ordered so the headline (E1) lands as early as possible.
# Each phase writes evidence/ and commits it, so a crash or a destroyed droplet never loses finished work.
#
#   bash deploy/run_session.sh m0        # doctor, Token Factory models, image + audio smoke tests
#   bash deploy/run_session.sh e15       # ASR choice + guard_ms on DEV data; applies the decision (commit)
#   bash deploy/run_session.sh dev       # full pipeline on every dev + adversarial clip (records E13 replay set)
#   bash deploy/run_session.sh freeze    # freeze prompts/constants/lexicons (after looking at dev output only)
#   bash deploy/run_session.sh e01       # headline on the TEST set (3 seeds), never used for tuning
#   bash deploy/run_session.sh core      # E11, E13 (prefix on), E14, E9, E10 (root)
#   bash deploy/run_session.sh ladder    # E2 V0..V5 (restarts servers per step) + E13 prefix off
#   bash deploy/run_session.sh quality   # E4, E5, E7 (+ E6 if the question files exist)
#   bash deploy/run_session.sh e03       # smaller Gemma with checks vs 31B without (own server config)
#   bash deploy/run_session.sh soak      # E8, 4 hours (run while people review)
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
set -a; [ -f .env ] && source .env; set +a
export ACCESSCAST_WORKER_PYTHON="${ACCESSCAST_WORKER_PYTHON:-$PWD/workers/.venv/bin/python}"
UV="uv run"
phase="${1:?phase: m0|e15|dev|freeze|e01|core|ladder|quality|e03|soak}"

commit() {  # commit evidence after every phase; never commit media or W3C-derived text
  git add evidence/*.json evidence/*.jsonl deploy/versions.lock src/accesscast/constants.py 2>/dev/null || true
  git commit -qm "$1" || true
  git push -q || echo "push failed (commit is local; push later)"
}

case "$phase" in
m0)
  bash deploy/healthcheck.sh
  $UV accesscast doctor --deep --json > evidence/doctor.json || true
  if [ -n "${AMD_TF_API_KEY:-}" ]; then
    curl -fsS -H "Authorization: Bearer $AMD_TF_API_KEY" "$AMD_TF_BASE_URL/models" > evidence/tokenfactory_models.json \
      || echo '{"error":"GET /models failed"}' > evidence/tokenfactory_models.json
  fi
  $UV python scripts/m0_smoke.py
  commit "M0: doctor, Token Factory model list, Gemma image + audio smoke tests"
  ;;
e15)
  $UV python -m eval.e15_asr --n 100
  $UV python scripts/apply_e15_decision.py
  commit "E15 (dev): ASR choice, aligner, guard_ms applied"
  ;;
dev)
  export ACCESSCAST_RECORD_REPLAY="$PWD/logs/replay"
  for v in data/dev/*.mp4 data/adversarial/*.mp4; do
    echo "== $v"; $UV accesscast run "$v" --strict-provider --require-rocm || echo "FAILED: $v"
  done
  $UV python scripts/dev_report.py   # summary of dev drafts/violations for prompt iteration (dev only)
  ;;
freeze)
  git status --porcelain | grep -q . && { echo "commit changes first"; exit 2; }
  $UV python scripts/freeze_prompts.py && git push -q --tags && git push -q
  ;;
e01)
  $UV python -m eval.e01_verifier_ab --split test --seeds 3
  commit "E1 (test, frozen): verifier A/B/C"
  ;;
core)
  $UV python -m eval.e11_adversarial --k 20
  $UV python -m eval.e13_serving --replay logs/replay --label prefix_on --subset even
  $UV python -m eval.e14_cost
  $UV python -m eval.e09_determinism
  sudo -E env PATH="$PATH" $UV python -m eval.e10_offline || true
  $UV python scripts/memory_table.py
  commit "E11, E13, E14, E9, E10 on MI300X"
  ;;
ladder)
  restart() { PREFIX="$1" EXTRA_31B="${2:-}" bash deploy/serve_gemma.sh; }
  restart --no-enable-prefix-caching;  $UV python -m eval.e13_serving --replay logs/replay --label prefix_off --subset odd
  ACCESSCAST_CONCURRENCY=1 $UV python -m eval.e02_ladder --step V0 --change "servers resident, one request at a time, no prefix cache"
  $UV python -m eval.e02_ladder --step V1 --change "requests in flight (semaphore 16)"
  restart --enable-prefix-caching;     $UV python -m eval.e02_ladder --step V2 --change "prefix caching"
  VLLM_ROCM_USE_AITER=1 restart --enable-prefix-caching; $UV python -m eval.e02_ladder --step V4 --change "VLLM_ROCM_USE_AITER=1" || true
  restart --enable-prefix-caching "--kv-cache-dtype fp8"; $UV python -m eval.e02_ladder --step V5 --change "FP8 KV cache" || true
  restart --enable-prefix-caching
  commit "E2 ladder and E13 prefix-cache A/B"
  ;;
quality)
  $UV python -m eval.e04_translation
  $UV python -m eval.e05_easyread --split test
  $UV python -m eval.e07_similarity --split test
  ls eval/questions/perspectives_*.json >/dev/null 2>&1 && $UV python -m eval.e06_questions || echo "E6 skipped: no question files yet"
  commit "E4, E5, E7 (and E6 if questions exist)"
  ;;
e03)
  docker rm -f g4-31b g4-e4b >/dev/null 2>&1 || true
  echo "start google/gemma-4-26B-A4B-it as gemma-4-26b on :8000, then:"
  echo "  ACCESSCAST_LOCAL_MODEL=gemma-4-26b $UV python -m eval.e01_verifier_ab --split test --seeds 3 --experiment-name e03_model_size_26b"
  ;;
soak)
  $UV python -m eval.e08_soak --hours 4 --concurrency 2
  commit "E8 soak"
  ;;
*) echo "unknown phase $phase"; exit 2 ;;
esac
