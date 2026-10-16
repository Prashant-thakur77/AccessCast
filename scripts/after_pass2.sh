#!/usr/bin/env bash
# Tonight's sequence (16 Oct): when dev pass 2 ends, stop the batch, run E15 on the accelerator, then one final dev
# pass with every fix on 8 representative clips. Then a person/agent reads the drafts and freezes.
cd "$(dirname "$0")/.."
until grep -q "^== pass 3" logs/dev_batch.log; do sleep 30; done
for p in $(pgrep -f "scripts/dev_local[.]sh") $(pgrep -f "bin/accesscast run data/"); do kill "$p" 2>/dev/null; done
sleep 5
echo "== E15 $(date -u +%FT%TZ)"
bash scripts/capped.sh bash scripts/run_local_session.sh e15
echo "== final dev pass $(date -u +%FT%TZ)"
ACCESSCAST_ASR_MODEL="$(uv run python -c 'from accesscast import constants as C; print(C.ASR_MODEL)')" \
ACCESSCAST_PROJECTS_DIR=projects/_dev bash scripts/capped.sh bash scripts/dev_local.sh data/adversarial/*.mp4 \
  data/dev/nasa_GSFC_20170614_Eclipse_m12534_Plane.mp4 data/dev/blender_sintel_trailer.mp4 \
  data/dev/nasa_GSFC_20130918_AACS_m11356_Food.mp4 data/dev/prelinger_Operator1949_2.mp4 \
  data/dev/nasa_GSFC_20171115_m12776_LifeInTheUniverse.mp4
echo "== done $(date -u +%FT%TZ)"
