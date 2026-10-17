#!/usr/bin/env bash
# Run the caption and voice-over stages (which now include Spanish and French) on the site drafts, then re-render.
set -uo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
export ACCESSCAST_PROJECTS_DIR=projects/_site ACCESSCAST_WORKER_PYTHON=$PWD/workers/.venv-gpu/bin/python ACCESSCAST_WORKER_DEVICE=gpu ACCESSCAST_REVIEW_POLICY=prototype-auto
for id in "$@"; do
  for st in captions voiceover review_init; do
    uv run accesscast stage $st -p $id --provider tokenfactory > logs/addlang_${id}_$st.log 2>&1; echo "$id $st exit $?"
  done
  uv run accesscast render -p $id --mode draft > logs/addlang_${id}_render.log 2>&1; echo "$id render exit $?"
done
echo ADD-LANGS-DONE
