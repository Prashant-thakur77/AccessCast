#!/usr/bin/env bash
# Dev runs without a droplet (docs/decisions.md D-021): Gemma 4 31B on AMD Token Factory; Whisper, the aligner
# and the voices on this workstation. ACCESSCAST_AUDIO_MODEL=none records that the E4B stages did not run.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [ -f .env ] && source .env; set +a
export ACCESSCAST_AUDIO_MODEL=none ACCESSCAST_SOUND_MODEL=ast  # D-021, D-022
export ACCESSCAST_ASR_MODEL="${ACCESSCAST_ASR_MODEL:-openai/whisper-large-v3-turbo}"
export ACCESSCAST_PROJECTS_DIR="${ACCESSCAST_PROJECTS_DIR:-projects/_dev}"
if [ -x workers/.venv-gpu/bin/python ]; then
  export ACCESSCAST_WORKER_PYTHON="$PWD/workers/.venv-gpu/bin/python" ACCESSCAST_WORKER_DEVICE=gpu
fi
export ACCESSCAST_RECORD_REPLAY="$PWD/logs/replay_tf"
export ACCESSCAST_LLM_CACHE="${ACCESSCAST_LLM_CACHE:-$PWD/logs/llm_cache}"
# Two passes: Token Factory drops requests for minutes at a time; the second pass replays every answer that
# succeeded (ACCESSCAST_LLM_CACHE) and asks again only for the calls that failed.
for pass in 1 2; do
  for v in "$@"; do
    bash scripts/tf_wait.sh 720 >/dev/null || { echo "Token Factory down for 24 h; stopping"; exit 5; }
    echo "== pass $pass: $v"; uv run accesscast run "$v" --provider tokenfactory --strict-provider || echo "FAILED: $v"
  done
done
