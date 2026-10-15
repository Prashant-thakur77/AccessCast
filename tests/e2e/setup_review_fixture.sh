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

dest="$(mktemp -d "${TMPDIR:-/tmp}/accesscast-review-e2e.XXXXXX")"
trap 'rm -rf "$dest"' EXIT
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
export ACCESSCAST_WORKER_MODE=fake
export ACCESSCAST_PROJECTS_DIR="$dest"
# Not exec: the EXIT trap removes the copy when the server stops.
uv run accesscast review --host 127.0.0.1 --port "$port"
