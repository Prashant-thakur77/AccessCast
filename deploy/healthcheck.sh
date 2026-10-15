#!/usr/bin/env bash
set -euo pipefail
for p in 8000 8001; do printf "%s " "$p"; curl -fsS --max-time 10 "http://127.0.0.1:$p/v1/models" | head -c 300; echo; done
