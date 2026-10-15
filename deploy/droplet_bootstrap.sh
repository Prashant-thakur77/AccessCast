#!/usr/bin/env bash
# Take a fresh AMD Developer Cloud MI300X "vLLM Quick Start" droplet to a serving state in one command.
# Run on the droplet as root from the repo checkout:  bash deploy/droplet_bootstrap.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export DEBIAN_FRONTEND=noninteractive
echo "== system packages"
apt-get update -qq && apt-get install -y -qq ffmpeg tesseract-ocr tesseract-ocr-hin tesseract-ocr-ita espeak-ng \
  fonts-dejavu-core fonts-noto-core jq git curl rsync nftables >/dev/null
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
[ -f .env ] || cp .env.example .env
set -a; source .env; set +a
: "${HF_TOKEN:?put HF_TOKEN in .env first}"
echo "== GPU"
(amd-smi static --asic --vram 2>/dev/null || rocm-smi --showproductname --showmeminfo vram) | tee logs_gpu_static.txt || true
echo "== pick a working vLLM ROCm image (PLAN §14.2 order)"
pick_image() {
  for img in "vllm/vllm-openai-rocm:gemma4" "rocm/vllm:rocm10.1.0_ubuntu24.04_py3.14-pytorch_2.13.0_vllm-0.29.0" \
             "vllm/vllm-openai-rocm:nightly"; do
    if docker pull -q "$img" >/dev/null 2>&1; then echo "$img"; return 0; fi
  done
  return 1
}
IMAGE="${IMAGE:-$(pick_image)}" || { echo "no image could be pulled"; exit 4; }
DIGEST=$(docker image inspect --format '{{index .RepoDigests 0}}' "$IMAGE")
VLLM_VER=$(docker run --rm --entrypoint python3 "$IMAGE" -c "import vllm;print(vllm.__version__)" 2>/dev/null || echo unknown)
ROCM_VER=$(cat /opt/rocm/.info/version 2>/dev/null || echo unknown)
cat > deploy/versions.lock <<LOCK
image=$IMAGE
digest=$DIGEST
vllm=$VLLM_VER
host_rocm=$ROCM_VER
recorded=$(date -u +%FT%TZ)
LOCK
echo "== project env + worker env (ROCm torch)"
uv sync --all-extras
( cd workers && uv venv -q --python 3.12 && uv pip install -q --index-url https://download.pytorch.org/whl/rocm6.4 torch torchaudio \
  && uv pip install -q transformers kokoro "misaki[en]" silero-vad soundfile numpy jiwer )
echo "== prefetch weights"
docker run --rm -v "$HOME/.cache/huggingface:/root/.cache/huggingface" -e HF_TOKEN --entrypoint huggingface-cli "$IMAGE" \
  download google/gemma-4-31B-it google/gemma-4-E4B-it >/dev/null || \
  uv run --with huggingface_hub huggingface-cli download google/gemma-4-31B-it google/gemma-4-E4B-it >/dev/null
( cd workers && .venv/bin/python -c "import torchaudio; torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H.get_model(); from silero_vad import load_silero_vad; load_silero_vad(); from transformers import pipeline; [pipeline('automatic-speech-recognition', model=m) for m in ('openai/whisper-large-v3','openai/whisper-large-v3-turbo')]; from kokoro import KPipeline; [KPipeline(lang_code=l, repo_id='hexgrad/Kokoro-82M') for l in 'ahi']" )
echo "== serve"
IMAGE="$IMAGE" bash deploy/serve_gemma.sh
echo "== doctor"
ACCESSCAST_WORKER_PYTHON=workers/.venv/bin/python uv run accesscast doctor --deep --json > evidence/doctor.json || true
jq -r '.checks[] | "\(.ok) \(.name): \(.detail)"' evidence/doctor.json
