#!/usr/bin/env bash
# Dev runs without a droplet (docs/decisions.md D-021): Gemma 4 31B on AMD Token Factory; Whisper, the aligner
# and the voices on this workstation. ACCESSCAST_AUDIO_MODEL=none records that the E4B stages did not run.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [ -f .env ] && source .env; set +a
export ACCESSCAST_AUDIO_MODEL=none
export ACCESSCAST_ASR_MODEL="${ACCESSCAST_ASR_MODEL:-openai/whisper-large-v3-turbo}"
export ACCESSCAST_PROJECTS_DIR="${ACCESSCAST_PROJECTS_DIR:-projects/_dev}"
if [ -x workers/.venv-gpu/bin/python ]; then
  export ACCESSCAST_WORKER_PYTHON="$PWD/workers/.venv-gpu/bin/python" ACCESSCAST_WORKER_DEVICE=gpu
fi
export ACCESSCAST_RECORD_REPLAY="$PWD/logs/replay_tf"
for v in "$@"; do
  echo "== $v"; uv run accesscast run "$v" --provider tokenfactory --strict-provider || echo "FAILED: $v"
done
