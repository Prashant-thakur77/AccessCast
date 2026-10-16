#!/usr/bin/env bash
# After E15 has applied its ASR decision: one dev pass with every fix on 13 representative clips (dev only).
cd "$(dirname "$0")/.."
until grep -qE "^E15 (OK|FAILED)" logs/e15_run3.log 2>/dev/null; do sleep 30; done
grep -q "^E15 OK" logs/e15_run3.log || { echo "E15 failed; not running the final dev pass"; exit 7; }
echo "== final dev pass $(date -u +%FT%TZ) asr=$(uv run python -c 'from accesscast import constants as C; print(C.ASR_MODEL)')"
ACCESSCAST_ASR_MODEL="$(uv run python -c 'from accesscast import constants as C; print(C.ASR_MODEL)')" \
ACCESSCAST_PROJECTS_DIR=projects/_dev bash scripts/capped.sh bash scripts/dev_local.sh data/adversarial/*.mp4 \
  data/dev/nasa_GSFC_20170614_Eclipse_m12534_Plane.mp4 data/dev/blender_sintel_trailer.mp4 \
  data/dev/nasa_GSFC_20130918_AACS_m11356_Food.mp4 data/dev/prelinger_Operator1949_2.mp4 \
  data/dev/nasa_GSFC_20171115_m12776_LifeInTheUniverse.mp4
echo "== done $(date -u +%FT%TZ)"
