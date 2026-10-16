#!/usr/bin/env bash
# The experiments without a droplet (docs/decisions.md D-021, D-022): Gemma 4 31B on AMD Token Factory; Whisper,
# the aligner, AST, the voices and the metric models on our workstation. Each phase writes evidence/ and commits it.
#
#   bash scripts/run_local_session.sh e15       # ASR choice + guard_ms on DEV data (workstation), applied
#   bash scripts/run_local_session.sh freeze    # freeze prompts/constants/lexicons/src (after dev review only)
#   bash scripts/run_local_session.sh e01       # headline on the TEST set (3 seeds), never used for tuning
#   bash scripts/run_local_session.sh e11       # live attacks, fresh seed per try, no answer cache
#   bash scripts/run_local_session.sh e09       # determinism: 3 fresh runs of 2 dev clips, no answer cache
#   bash scripts/run_local_session.sh e13       # Token Factory client-side latency and tokens/s
#   bash scripts/run_local_session.sh e14       # Gemma tokens per finished minute, from the dev runs' call logs
#   bash scripts/run_local_session.sh quality   # E4, E5, E7 (+ E6 if the question files exist)
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [ -f .env ] && source .env; set +a
export ACCESSCAST_AUDIO_MODEL=none ACCESSCAST_SOUND_MODEL=ast ACCESSCAST_PROVIDER=tokenfactory
if [ -x workers/.venv-gpu/bin/python ]; then
  export ACCESSCAST_WORKER_PYTHON="$PWD/workers/.venv-gpu/bin/python" ACCESSCAST_WORKER_DEVICE=gpu
fi
UV="uv run"
phase="${1:?phase: e15|freeze|e01|e11|e09|e13|e14|quality}"

commit() {  # evidence only; never media or W3C-derived text
  git add evidence/*.json evidence/*.jsonl src/accesscast/constants.py 2>/dev/null || true
  git commit -qm "$1" || true
  git pull -q --rebase && git push -q || echo "push failed (commit is local; push later)"
}
tf_up() { bash scripts/tf_wait.sh 720 >/dev/null || { echo "Token Factory down for 24 h"; exit 5; }; }

case "$phase" in
e15)
  $UV python -m eval.e15_asr --n 100 --no-gemma --no-rocm
  $UV python scripts/apply_e15_decision.py
  commit "E15 (dev, workstation): ASR choice and guard_ms applied"
  ;;
freeze)
  git status --porcelain | grep -q . && { echo "commit changes first"; exit 2; }
  $UV python scripts/freeze_prompts.py && git push -q --tags && git push -q
  ;;
e01)
  tf_up
  ACCESSCAST_LLM_CACHE="$PWD/logs/llm_cache_test" \
    $UV python -m eval.e01_verifier_ab --split test --seeds 3 --provider tokenfactory
  commit "E1 (test, frozen): verifier A/B/C, Gemma 4 31B on AMD Token Factory"
  ;;
e11)
  tf_up
  $UV python -m eval.e11_adversarial --k 20 --provider tokenfactory
  commit "E11 live attacks, Gemma 4 31B on AMD Token Factory"
  ;;
e09)
  tf_up
  $UV python -m eval.e09_determinism --runs 3 --no-rocm \
    --clips nasa_GSFC_20170614_Eclipse_m12534_Plane,blender_sintel_trailer
  commit "E9 determinism (dev), Token Factory"
  ;;
e13)
  tf_up
  $UV python -m eval.e13_tokenfactory --replay logs/replay_tf --levels 1,4 --repeats 3 --per-level 20
  commit "E13 Token Factory client-side latency and throughput"
  ;;
e14)
  $UV python -m eval.e14_tokens --projects projects/_dev
  commit "E14 Gemma tokens per finished minute (dev call logs)"
  ;;
quality)
  tf_up
  # each experiment stands alone: one failing (e.g. FLORES+ not accessible) never stops the others
  $UV python -m eval.e04_translation --provider tokenfactory --allow-cpu || echo "E4 failed (evidence written)"
  $UV python -m eval.e05_easyread --split test --provider tokenfactory --allow-cpu || echo "E5 failed (evidence written)"
  $UV python -m eval.e07_similarity --split test --provider tokenfactory --allow-cpu || echo "E7 failed (evidence written)"
  ls eval/questions/perspectives_*.json >/dev/null 2>&1 && $UV python -m eval.e06_questions --provider tokenfactory \
    || echo "E6 skipped: no question files yet"
  commit "E4, E5, E7 (and E6 if questions exist), Token Factory"
  ;;
*) echo "unknown phase $phase"; exit 2 ;;
esac
