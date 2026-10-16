#!/usr/bin/env bash
# 17 Oct after test-freeze-4: E9 (determinism, dev) with the render fixes, then E5 and E7 (test) again.
cd "$(dirname "$0")/.."
echo "== e09 $(date -u +%FT%TZ)"; bash scripts/capped.sh bash scripts/run_local_session.sh e09; echo "== e09 exit $?"
set -a; source .env; set +a
export ACCESSCAST_AUDIO_MODEL=none ACCESSCAST_SOUND_MODEL=ast ACCESSCAST_PROVIDER=tokenfactory
export ACCESSCAST_WORKER_PYTHON="$PWD/workers/.venv-gpu/bin/python" ACCESSCAST_WORKER_DEVICE=gpu
echo "== e05 $(date -u +%FT%TZ)"
bash scripts/capped.sh uv run python -m eval.e05_easyread --split test --provider tokenfactory --allow-cpu; echo "== e05 exit $?"
echo "== e07 $(date -u +%FT%TZ)"
bash scripts/capped.sh uv run python -m eval.e07_similarity --provider tokenfactory --allow-cpu --judge-model Qwen3.8-27B; echo "== e07 exit $?"
git add evidence/*.json evidence/*.jsonl && git commit -qm "E9 (dev), E5 and E7 (test) under test-freeze-4" && git pull -q --rebase && git push -q
echo "== chain4 done $(date -u +%FT%TZ)"
