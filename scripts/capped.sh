#!/usr/bin/env bash
# Run a long AccessCast job with a hard memory cap (cgroup v2, no root): if it grows past the cap the kernel kills
# this job, never the editor or the desktop. Our pipeline treats a killed worker as a failed stage (fail closed).
#   bash scripts/capped.sh bash scripts/run_local_session.sh e01
set -euo pipefail
CAP="${ACCESSCAST_MEMORY_MAX:-7G}"
exec systemd-run --user --scope --quiet -p MemoryMax="$CAP" -p MemorySwapMax=1G -p OOMPolicy=continue \
  bash -c 'echo 1000 > /proc/self/oom_score_adj; exec "$@"' _ "$@"
