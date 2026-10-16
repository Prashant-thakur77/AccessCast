#!/usr/bin/env bash
# After chain 1 (E9 done): E11 again (scoring fix for extended lines), then the quality phase.
cd "$(dirname "$0")/.."
until grep -q "^== chain done" logs/chain.log; do sleep 30; done
for phase in e11 quality; do
  echo "== $phase $(date -u +%FT%TZ)"
  bash scripts/capped.sh bash scripts/run_local_session.sh "$phase"; echo "== $phase exit $?"
done
echo "== chain2 done $(date -u +%FT%TZ)"
