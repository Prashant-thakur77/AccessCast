#!/usr/bin/env bash
# Start the review server (PLAN §12) on a fresh copy of a test project, for playwright.review.config.ts.
#
#   ACCESSCAST_REVIEW_FIXTURE  a projects folder (holding <sha12>/ project folders) or one project folder.
#                              Copied, never modified, so every test run starts from the same state.
#   ACCESSCAST_REVIEW_PORT     port to bind on 127.0.0.1 (default 8091).
set -euo pipefail

src="${ACCESSCAST_REVIEW_FIXTURE:?set ACCESSCAST_REVIEW_FIXTURE to a review test project folder}"
port="${ACCESSCAST_REVIEW_PORT:-8091}"
if [[ ! -d "$src" ]]; then
  echo "setup_review_fixture: $src is not a folder" >&2
  exit 3
fi

# One fixed folder per port, wiped at each start (Playwright may SIGKILL us, so no exit trap is relied on).
dest="${TMPDIR:-/tmp}/accesscast-review-e2e-$port"
rm -rf "$dest"
mkdir -p "$dest"
if [[ -f "$src/project.json" ]]; then
  cp -r "$src" "$dest/$(basename "$src")"
else
  cp -r "$src"/. "$dest"/
fi
if ! ls "$dest"/*/project.json >/dev/null 2>&1; then
  echo "setup_review_fixture: no project.json found under $src" >&2
  exit 3
fi

cd "$(dirname "$0")/../.."
unset VIRTUAL_ENV
# Start from a manual review (every line waits for a person), whatever policy built the fixture: the public demo
# fixture is built with prototype-auto, which would leave nothing to review.
rm -rf "$dest"/*/review
uv run python -c 'import sys; from pathlib import Path; from accesscast.review.store import ReviewStore
[ReviewStore(p).init_from_items() for p in Path(sys.argv[1]).iterdir() if (p / "items").is_dir()]' "$dest"
export ACCESSCAST_WORKER_MODE=fake
export ACCESSCAST_PROJECTS_DIR="$dest"
exec uv run accesscast review --host 127.0.0.1 --port "$port"
