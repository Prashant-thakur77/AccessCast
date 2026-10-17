# AccessCast — see CLAUDE.md §4. Every target is safe to re-run.
SHELL := /bin/bash
UV := env -u VIRTUAL_ENV uv
AC := $(UV) run accesscast
PROJECT ?=
VIDEO ?=
EXP = $(UV) run python -m eval.$(1)

.PHONY: setup check lint typecheck test test-e2e demo-fixture serve-gemma tunnel doctor run review render \
        export-site freeze-prompts offline-demo claims-check submission-check schemas fixture calibrate \
        e01 e02 e03 e04 e05 e06 e07 e08 e09 e10 e11 e12 e13 e14 e15 e16

setup:  ## uv sync, worker env, pre-fetched TTS/NLP assets, node deps
	$(UV) sync --all-extras
	cd workers && $(UV) sync
	cd workers/indic && $(UV) sync  # E4 Hindi baseline (IndicTrans2 needs transformers 4)
	cd workers && $(UV) run python -c "from kokoro import KPipeline; [KPipeline(lang_code=l, repo_id='hexgrad/Kokoro-82M') for l in 'ahi']"
	cd workers && $(UV) run python -c "import torchaudio; torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H.get_model(); from silero_vad import load_silero_vad; load_silero_vad()"
	cd workers && $(UV) run python -c "from transformers import pipeline; [pipeline('automatic-speech-recognition', model=m) for m in ('openai/whisper-large-v3', 'openai/whisper-large-v3-turbo')]"
	-npm install --no-audit --no-fund
	-$(UV) run pre-commit install 2>/dev/null || true

lint:
	$(UV) run ruff check src tests eval workers scripts
	$(UV) run ruff format --check src tests eval workers scripts

typecheck:
	$(UV) run mypy

test:
	$(UV) run pytest

check: lint typecheck test

test-e2e:
	npx playwright test

schemas:
	$(AC) schemas-export

fixture:  ## rebuild the 20 s synthetic fixture (Kokoro voices + generated visuals)
	cd workers && $(UV) run python ../scripts/make_fixture.py

calibrate:
	$(AC) calibrate-tts

demo-fixture:  ## whole pipeline in fake mode on the committed fixture, then serve the player
	$(AC) demo-fixture --port 8080

serve-gemma:  ## on the droplet only
	bash deploy/serve_gemma.sh

tunnel:
	@echo "ssh -N -L 8000:127.0.0.1:8000 -L 8001:127.0.0.1:8001 root@$${DROPLET_IP:-<droplet-ip>}"

doctor:
	mkdir -p evidence && $(AC) doctor --deep --json > evidence/doctor.json; cat evidence/doctor.json | head -40

run:
	@test -n "$(VIDEO)" || (echo "usage: make run VIDEO=path" && exit 2)
	$(AC) run "$(VIDEO)" --strict-provider

review:
	$(AC) review --port 8081

render:
	@test -n "$(PROJECT)" || (echo "usage: make render PROJECT=<sha12>" && exit 2)
	$(AC) render --project $(PROJECT) --mode public

export-site:
	$(AC) export-site

freeze-prompts:
	$(UV) run python scripts/freeze_prompts.py

claims-check:
	$(AC) claims-check

submission-check:
	$(UV) run python scripts/submission_check.py

offline-demo:  ## on the droplet, as root: both guard layers
	$(UV) run python -m eval.e10_offline

e01 e02 e03 e04 e05 e06 e07 e08 e09 e10 e11 e12 e13 e14 e15 e16:
	$(UV) run python -m eval.run $@
