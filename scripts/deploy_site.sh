#!/usr/bin/env bash
# Build and deploy the public site: player pages and the reviewed (or watermarked fixture) projects, the claims,
# the proof page's recorded E11 run, the rule examples, and the live proof API function (D-028).
set -euo pipefail
cd "$(dirname "$0")/.."
# the public site shows real Gemma output only: the synthetic fake-mode fixture stays in the local demo and tests
PROJECTS="${SITE_PROJECTS:-projects/_site}"; IDS="${SITE_IDS:-cbf141ec3213,dac08bcd9d7a,8af59806d6b6}"; DRAFTS="${SITE_ALLOW_DRAFTS:---allow-drafts}"
ACCESSCAST_PROJECTS_DIR="$PROJECTS" uv run accesscast export-site --projects "$IDS" $DRAFTS
uv run python scripts/build_proof_record.py
uv run python scripts/build_rule_examples.py >/dev/null
printf '{"api_base": "https://accesscast.vercel.app"}\n' > site/data/proof_config.json
[ -d site/api/_vendor ] || bash scripts/build_vercel_api.sh
rsync -a --delete --exclude "__pycache__" --exclude "player/static" --exclude "review/static" src/accesscast site/api/_vendor/
# which commit is live: the live check compares it with this checkout, so a deploy that silently failed shows up
printf '{"commit": "%s", "built_at": "%s"}\n' "$(git rev-parse --short HEAD)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > site/data/build.json
(cd site && vercel deploy --prod --yes > ../logs/vercel.log 2>&1) || true
grep -E "Aliased|readyState" logs/vercel.log || true
grep -q '"readyState": "READY"' logs/vercel.log || { echo "VERCEL DEPLOY FAILED: see logs/vercel.log"; tail -n 20 logs/vercel.log; exit 1; }
uv run python scripts/live_check.py || echo "LIVE CHECK FAILED (evidence/live_check.json)"
