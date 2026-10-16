#!/usr/bin/env bash
# After E1 (17 Oct): quality (E4, E5, E7 on test), then E11 live attacks, then E9 determinism. Each capped.
cd "$(dirname "$0")/.."
for phase in quality e11 e09; do
  echo "== $phase $(date -u +%FT%TZ)"
  bash scripts/capped.sh bash scripts/run_local_session.sh "$phase"; echo "== $phase exit $?"
done
echo "== chain done $(date -u +%FT%TZ)"
