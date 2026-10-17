#!/usr/bin/env bash
# Build and deploy the public site: player pages and the reviewed (or watermarked fixture) projects, the claims,
# the proof page's recorded E11 run, the rule examples, and the live proof API function (D-028).
set -euo pipefail
cd "$(dirname "$0")/.."
PROJECTS="${SITE_PROJECTS:-projects/_fixture}"; IDS="${SITE_IDS:-ed26561ae9d7}"; DRAFTS="${SITE_ALLOW_DRAFTS:---allow-drafts}"
ACCESSCAST_PROJECTS_DIR="$PROJECTS" uv run accesscast export-site --projects "$IDS" $DRAFTS
uv run python scripts/build_proof_record.py
uv run python scripts/build_rule_examples.py >/dev/null
printf '{"api_base": "https://accesscast.vercel.app"}\n' > site/data/proof_config.json
[ -d site/api/_vendor ] || bash scripts/build_vercel_api.sh
rsync -a --delete --exclude "__pycache__" --exclude "player/static" --exclude "review/static" src/accesscast site/api/_vendor/
(cd site && vercel deploy --prod --yes 2>&1 | grep -E "Aliased|readyState|Error" )
uv run python scripts/live_check.py || echo "LIVE CHECK FAILED (evidence/live_check.json)"
