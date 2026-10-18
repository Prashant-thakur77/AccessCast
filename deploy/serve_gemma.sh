#!/usr/bin/env bash
# Start Gemma 4 31B (port 8000) then E4B (port 8001) with vLLM on ROCm, bound to 127.0.0.1 only.
# Usage: IMAGE=<image> bash deploy/serve_gemma.sh   (default: first image in deploy/versions.lock that works)
set -euo pipefail
cd "$(dirname "$0")/.."
IMAGE="${IMAGE:-$(grep -E '^image=' deploy/versions.lock | head -1 | cut -d= -f2)}"
HF_CACHE="${HF_CACHE:-$HOME/.cache/huggingface}"
GPU_UTIL_31B="${GPU_UTIL_31B:-0.55}"
GPU_UTIL_E4B="${GPU_UTIL_E4B:-0.15}"
EXTRA_31B="${EXTRA_31B:-}"     # e.g. "--attention-backend TRITON_ATTN" if the default backend fails (see incidents.md)
PREFIX="${PREFIX:---enable-prefix-caching}"   # E2 V0 uses --no-enable-prefix-caching
mkdir -p logs/vllm "$HF_CACHE"

common=(--ipc=host --network=host --privileged --cap-add=CAP_SYS_ADMIN --cap-add=SYS_PTRACE
        --device=/dev/kfd --device=/dev/dri --group-add=video --security-opt=seccomp=unconfined --shm-size 16G
        -v "$HF_CACHE:/root/.cache/huggingface" -e HF_TOKEN -e VLLM_NO_USAGE_STATS=1 -e DO_NOT_TRACK=1
        -e HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-0}")

wait_healthy() {  # port model-name container
  local port=$1 name=$2 ctr=$3
  for i in $(seq 1 480); do
    if curl -fsS --max-time 10 "http://127.0.0.1:${port}/v1/models" | grep -q "$name"; then
      echo "$name healthy on 127.0.0.1:$port after $((i*5)) s"; return 0; fi
    if ! docker ps --format '{{.Names}}' | grep -qx "$ctr"; then
      echo "container $ctr exited; last log lines:"; docker logs --tail 60 "$ctr" 2>&1 | tail -60; return 5; fi
    sleep 5
  done
  echo "$name not healthy after 2400 s"; docker logs --tail 60 "$ctr"; return 5
}

docker rm -f g4-31b g4-e4b >/dev/null 2>&1 || true
docker run -d --name g4-31b "${common[@]}" -e VLLM_CACHE_ROOT=/root/.cache/vllm-31b "$IMAGE" \
  --model google/gemma-4-31B-it --served-model-name gemma-4-31b --host 127.0.0.1 --port 8000 \
  --max-model-len 32768 --gpu-memory-utilization "$GPU_UTIL_31B" \
  --limit-mm-per-prompt '{"image":16}' --mm-processor-kwargs '{"max_soft_tokens":140}' \
  $PREFIX --generation-config vllm --seed 0 $EXTRA_31B
( docker logs -f g4-31b > logs/vllm/g4-31b.log 2>&1 & )
wait_healthy 8000 gemma-4-31b g4-31b

docker run -d --name g4-e4b "${common[@]}" -e VLLM_CACHE_ROOT=/root/.cache/vllm-e4b "$IMAGE" \
  --model google/gemma-4-E4B-it --served-model-name gemma-4-e4b --host 127.0.0.1 --port 8001 \
  --max-model-len 16384 --gpu-memory-utilization "$GPU_UTIL_E4B" \
  --limit-mm-per-prompt '{"image":0,"audio":1}' --generation-config vllm --seed 0
( docker logs -f g4-e4b > logs/vllm/g4-e4b.log 2>&1 & )
wait_healthy 8001 gemma-4-e4b g4-e4b

# No silent CPU offload: fail if either server reports offload/swap.
if grep -iE "cpu_offload_gb=[1-9]|swap_space=[1-9]" logs/vllm/*.log; then echo "CPU offload active: refusing"; exit 6; fi
echo "both Gemma servers up (127.0.0.1 only). Reach them from a laptop with: make tunnel"
