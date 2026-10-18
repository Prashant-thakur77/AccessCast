# CLAUDE.md — how to work in the AccessCast repo

AccessCast turns one video into versions for different viewers: audio description fitted into the pauses in dialogue (extended description when the pauses are too short), SDH captions, easy-read captions, and Hindi and Italian versions. Gemma 4 on an AMD Instinct MI300X does the model work; code checks every line; Gemma repairs what fails; a person approves what the public hears.

We are building it to win AMD Developer Hackathon ACT III (lablab.ai), track "Create a New Kind of Experience", plus the Google prize for Gemma on AMD Developer Cloud + ROCm.

**`PLAN.md` is the source of truth for what to build.** This file is how to build it. Read all of `PLAN.md` before the first change, and re-read the relevant section before each task. If you change a design decision, update `PLAN.md` in the same commit and log it in `docs/decisions.md`.

---

## 1. Golden rules (never break these)

1. **No invented numbers.** Every number in README, JUDGES.md, the deck, the site or `docs/lablab.md` comes from a JSON file in `evidence/` written by a script in this repo, or is an outside fact registered with status `cited` (URL, access date, quoted text), and every one is registered in `evidence/public-claims.json`. If a number isn't measured yet, write `<pending: claim_id>`, never a guess; `make submission-check` fails while any placeholder remains. Estimates, list prices and "by memory accounting" comparisons are labelled as such every time they appear. Never state a result (in docs, the demo script or slides) before the experiment that measures it has run.
2. **Fail closed.** Exceptions, timeouts, malformed JSON, missing models, unknown languages, unreachable endpoints: the item is blocked and goes to review, the stage exits non-zero, nothing passes by default. Never write a default "pass" score on a parse error.
3. **The model proposes, code decides.** Gemma never decides timing or acceptability, and we never ask Gemma for its confidence. Confidence is computed in `confidence.py` from measured signals.
4. **The test set is sacred.** The W3C WAI videos are never used for tuning, including choosing the ASR model, ladder steps or thresholds. Don't open their outputs while iterating. Test-set runs happen only after `make freeze-prompts`, and each run is logged in `evidence/test_runs.jsonl`. If you need to look at failures to improve something, use the dev set. Say "never used for tuning", not "never seen" (Gemma may have seen public videos in pretraining).
5. **One change per experiment.** Every comparison names its baseline and changes exactly one thing. If two things changed, it is two experiments.
6. **No silent fallbacks.** No silent CPU fallback (`--require-rocm`), no silent model or provider switch (`--strict-provider` in all evals and benchmarks), no silent truncation of text, no silent fallback to English.
7. **Originality and licences.** Our code is MIT. (Changed 16 Oct 2026 on the team's instruction; see `docs/decisions.md` D-001.)
   - **Reuse code from MIT, Apache-2.0, BSD and similarly permissive repos directly** when that is faster or better, including other hackathon entries (earlier projects). Keep the original licence and copyright header on every reused file or block, add each reuse to `THIRD_PARTY_NOTICES.md`, and for Apache-2.0 code also carry its NOTICE content.
   - **an earlier project** ("All rights reserved") and **an earlier project** (no LICENSE file): read and learn from them, but write our own code. This is copyright law, not a preference.
   - Libraries installed as dependencies are used normally under their licences.
   - No non-commercial models, weights or voices (no XTTS-v2, no F5-TTS weights). Piper's code is GPL-3.0: only ever as a separate CLI process, never imported. Every model, voice, dataset, clip and font goes in `MODEL_LICENSES.md` with its licence and link before it is used.
8. **Secrets and media.** Keys live only in `.env` (git-ignored; `.env.example` lists names only). Never log keys, tokens or image bytes. Never commit W3C videos, FLORES+ data or any media we may not redistribute; commit manifests with SHA-256 instead. **W3C-derived outputs** (our versions of W3C videos) are never committed, never copied into `site/`, and never excerpted in the demo video, unless W3C confirms in writing that this is allowed.
9. **Never expose a Gemma endpoint to the internet.** vLLM binds to `127.0.0.1` on the droplet; reach it through an SSH tunnel. Docker port mapping bypasses the droplet firewall.
10. **Paid cloud resources (changed 16 Oct 2026; `docs/decisions.md` D-002).** If you have API access to AMD Developer Cloud, create and destroy the MI300X droplet yourself; otherwise ask the person to. Stay within the $100 credit. Snapshot, then destroy the droplet whenever GPU work is idle (it bills while powered off). Log every create/destroy with time and cost in `docs/decisions.md`.
11. **Honesty over polish.** Publish negative results with numbers. If Gemma never fails an adversarial case, say so. Never hand-craft a model failure and present it as live.
12. **Plain words for people.** Everything a judge, viewer or reviewer reads uses short sentences and everyday words. Give counts (k of N) next to percentages, and name the data split.
13. **Accessible by default.** Every page we ship works with a keyboard only, has labelled controls, announces changes through live regions, and passes axe-core with 0 violations.
14. **Scope is not cut to fit a schedule.** The priority labels in `PLAN.md` (P0/P1/P2) set the order of work, not whether something gets built. From milestone M3 on, `main` must always be submittable.

---

## 2. Facts you need

- Submission deadline: plan against **18 Oct 2026, 15:30 IST** (the page also shows 20:30; the earlier one is the safe one). Required fields: cover image, demo video, slide deck, public GitHub repo, demo platform, app URL.
- Judging: Application of Technology, Presentation, Business Value, Originality (each out of 5). Judges docked past winners for a sleeping demo and for a pitch too technical for non-technical judges.
- Hardware: one AMD Instinct MI300X (192 GB) on AMD Developer Cloud, $1.99/hour, plus AMD Token Factory (OpenAI-compatible; details unverified until `GET /models` runs; see `PLAN.md` §14.3).
- Gemma models: `google/gemma-4-31B-it` (text + image; main model) and `google/gemma-4-E4B-it` (audio input, 30 s per clip, no timestamps). Don't use `gemma-4-12B-it` (no ROCm support yet). Gemma does every vision, language and repair task; Whisper, the aligner, TTS and metric models are not Gemma, so never claim "Gemma does everything".
- Must-haves: `PLAN.md` §5. `make submission-check` enforces them.

---

## 3. Start of the first session

1. Read `PLAN.md` end to end.
2. Ask the person which prerequisites in `PLAN.md` §24 are done, and for `.env` values (never paste keys into chat logs or files other than `.env`).
3. Build milestone **M1 (skeleton)** first, in fake worker mode, so everything runs without a GPU: repo layout (§7), CLI with every stage stubbed, schemas, events log, unit-test CI, README/JUDGES/claims skeletons, `make claims-check` passing on an empty registry.
4. When the droplet is up, do **M0** with the person: serve Gemma (§14.2), run `accesscast doctor --deep`, save `evidence/tokenfactory_models.json` and `evidence/doctor.json`, pin images in `deploy/versions.lock`.
5. Then follow the milestones in `PLAN.md` §22 in order. Each milestone is done only when its exit criteria hold.

---

## 4. Commands (Makefile targets to create and keep working)

| Target | What it does |
|---|---|
| `make setup` | `uv sync`, install pre-commit hooks, pre-fetch TTS/NLP assets (Kokoro voices, espeak data, spaCy/stanza models) so offline runs work |
| `make check` | `ruff`, `mypy` (strict for `verify/`, `repair/`, `confidence.py`, `review/gate.py`), unit tests |
| `make test` / `make test-e2e` | unit + golden tests / Playwright end-to-end with axe-core |
| `make demo-fixture` | whole pipeline in fake mode on the committed 20 s fixture, then serve the player at `http://127.0.0.1:8080/?audience=judge` |
| `make serve-gemma` | (on the droplet) start the 31B and E4B containers with the flags in `PLAN.md` §14.2 and wait on the health loop |
| `make tunnel` | print the SSH tunnel command for ports 8000/8001 |
| `make doctor` | `accesscast doctor --deep --json > evidence/doctor.json` |
| `make run VIDEO=path` | all stages for one video into `projects/<sha12>/` |
| `make review` | start the review app on `127.0.0.1:8081` |
| `make render PROJECT=<sha12>` | gate + render all versions (refuses while anything is pending) |
| `make export-site` | copy reviewed projects into `site/` |
| `make freeze-prompts` | tag `test-freeze-<n>` and write `evidence/test_freeze.json` |
| `make e01` … `make e16` | run one experiment; writes `evidence/eNN_*.json` |
| `make offline-demo` | E10 on the droplet with both guard layers (Python sockets in every process, host-level egress counter) |
| `make claims-check` | verify every claim's hash and value; scan public files for unregistered numbers |
| `make submission-check` | everything in `PLAN.md` §18.6 |

---

## 5. Environment variables (`.env.example`)
```
ACCESSCAST_WORKER_MODE=real            # real | fake
ACCESSCAST_LOCAL_BASE_URL=http://127.0.0.1:8000/v1
ACCESSCAST_LOCAL_AUDIO_BASE_URL=http://127.0.0.1:8001/v1
ACCESSCAST_LOCAL_MODEL=gemma-4-31b
ACCESSCAST_LOCAL_AUDIO_MODEL=gemma-4-e4b
AMD_TF_BASE_URL=                       # confirm from the Token Factory console
AMD_TF_API_KEY=
AMD_TF_MAX_CONCURRENCY=8               # reported limit; measure
AMD_TF_RPM=30                          # reported limit; measure
HF_TOKEN=
GPU_HOURLY_COST_USD=1.99
ACCESSCAST_REVIEW_POLICY=manual        # manual | prototype-auto (drafts only)
ACCESSCAST_PROJECT_SEED=20261018
```

---

## 6. Code conventions

- Python 3.12, `uv`, `ruff` (format + lint), `mypy`, `pytest`, pydantic v2. Type hints everywhere.
- **Only `workers/*.py` import torch.** The core CLI talks to workers through versioned JSON request/response files written atomically (temp file, fsync, rename), with progress lines on stderr prefixed `@@AC_EVENT@@ {json}`. Workers support a one-shot mode and a resident daemon mode (local Unix socket, model stays loaded); see `PLAN.md` §6.3. LLM calls go over HTTP to vLLM, never in-process.
- Every stage reads files and writes files under `projects/<sha12>/`, is content-addressed, and can be re-run alone. Cache key = SHA-256 of stage name, stage version, config, sorted input hashes, model manifest, **seed, prompt SHA-256, sampling settings and the server-reported model id** (no paths, ids or timings), so repeated runs with new seeds are never served from cache.
- Every prompt returns a top-level JSON object (wrap lists as `{"items": [...]}`); JSON-object mode rejects bare arrays.
- Constants live in `constants.py`, each with a comment naming its source (e.g. `CPS_MAX_EN_SDH = 20  # Netflix English TTSG`).
- Verifier rules are small pure functions returning `Finding`s with observed vs threshold; one test file per rule with a passing and a failing fixture; every rule listed in `docs/rules.md` with its source.
- Seeds: `derive_seed(project_seed, label) = int(sha256(f"{project_seed}:{label}").hexdigest[:8], 16)`.
- Exit codes: 0 ok, 2 usage, 3 config, 4 missing dependency, 5 model endpoint, 6 out of memory, 7 validation failed, 8 media/TTS, 10 partial, 130 interrupted.
- Logs: `logs/events.jsonl` per project (`{"stage","ts","event",...}`); `logs/llm_calls.jsonl` per call (§14.3 of the plan).
- GPU timing: `torch.cuda.reset_peak_memory_stats` → `torch.cuda.synchronize` → `perf_counter` → work → `synchronize` → record `max_memory_allocated`. Put it in `bench/stage_timer.py` and use it for every GPU stage.
- Prompts are files in `src/accesscast/llm/prompts/`; never inline prompt text in Python.
- No new dependency without adding its licence to `MODEL_LICENSES.md` or `THIRD_PARTY_NOTICES.md`.

---

## 7. Evidence files

Every eval and benchmark writes one JSON file, **always, including when its checks fail** (set `"passed": false` and exit non-zero; never skip writing, or negative results disappear). Names use two digits: `e01_verifier_ab.json`, `e02_ladder.json`, …, `e16_ui_a11y.json`.
```json
{"schema":"accesscast/evidence/v1","experiment":"e01_verifier_ab","split":"test","passed":true,
 "git_commit":"…","freeze_tag":"test-freeze-1","started_at":"…","finished_at":"…",
 "environment":{"gpu":"AMD Instinct MI300X","rocm":"…","vllm":"…","image_digest":"…","torch":"…"},
 "config":{…},"results":[{…per item…}],"summary":{…}}
```
- Commit evidence files. Don't edit them by hand; re-run the script.
- After a run, add or update the claims that quote it in `evidence/public-claims.json` (pointer into `summary`), then run `make claims-check`.
- Benchmarks: discard the first run as warm-up, alternate arms, report the median of at least 3 runs with min and max, and keep quality numbers next to speed numbers.
- Benchmarks and evals always run with `--strict-provider` and record the server-reported model id.

---

## 8. Working with the droplet

- The person creates and destroys the droplet. You get an IP and SSH access.
- `deploy/droplet_bootstrap.sh` must take a fresh "vLLM Quick Start" droplet to a serving state in one command (pull images, start Gemma, install workers' Python env, pre-fetch models). Keep it working; the droplet will be rebuilt.
- Sync code with `git pull` on the droplet; sync projects back with `rsync`. Results that matter go into `evidence/` and get committed.
- Record VRAM with `amd-smi`/`rocm-smi` (utilisation, power and temperature read zero on these virtual GPUs; say so in docs).
- When you finish a block of GPU work, tell the person the droplet can be destroyed (after a snapshot if needed).

---

## 9. When something breaks

- Write a dated entry in `docs/incidents.md`: Symptom / Root cause / Fix. These feed the README's "Bugs that taught us something".
- If you are blocked on a person (account, key, data, a decision), say exactly what you need and continue with work that doesn't need it (fake mode, tests, docs, the review app, the player).
- Don't loop on the same failing command. After two failed attempts at the same fix, stop, write down what you tried, and ask.

---

## 10. Known pitfalls (from the stack research and winning repos)

- Gemma 4 needs `transformers >= 5.5.0`; older versions don't recognise `gemma4`.
- Gemma 4 on vLLM ROCm uses the Triton attention backend (`--attention-backend TRITON_ATTN`); decode can be slow, so get throughput from concurrency.
- Gemma 4 audio: only E2B/E4B/12B take audio; 30 s per clip; no timestamps. The ROCm image may need `pip install "vllm[audio]"`.
- vLLM's `latest` tag on `vllm/vllm-openai-rocm` may not exist; check tags before pulling.
- The FP8 Gemma checkpoint listed by vLLM is for NVIDIA Hopper/Blackwell, not AMD.
- ffmpeg `loudnorm` defaults to I = −24; always set `I` explicitly (−23 broadcast, −16 web).
- CUDA `flash_attn` wheels don't work on ROCm; don't install them.
- Kokoro fetched a spaCy model mid-run in an earlier project's project; pre-fetch everything in `make setup`. Kokoro needs `espeak-ng`.
- In an earlier project, six server workers replaying the same request produced very different outputs (52 vs 16 facts), and an ASR batch of 8 shifted forced-alignment timestamps. Measure determinism instead of assuming it; keep ASR batches small and re-test timestamps after any batching change.
- Whisper's word timestamps from transformers are not forced-aligned. Re-align (`PLAN.md` §9 S2) and measure boundary error on the hand-labelled dev clip before trusting the gap map.
- `tpad` only pads the end of a stream: extended description needs per-segment trim + pad + concat. `sidechaincompress` doesn't give a fixed dip: duck with a `volume` envelope at the known anchor times.
- vLLM sends usage stats by default: set `VLLM_NO_USAGE_STATS=1` and `DO_NOT_TRACK=1` in every container.
- Gemma 4 E4B returns no timestamps for audio, and the server takes one audio clip per prompt: one sound-event window per request.
- vLLM compile-cache collisions across different actions (an earlier project): use separate cache namespaces per server.
- Thinking mode made an earlier project 3.5× slower with worse output; keep thinking off unless an experiment shows otherwise.
- Browser support for switching audio tracks inside one file is limited: ship one MP4 per audience version.
- Only one `<track>` per kind + srclang + label: give each track a distinct label.
- Chatterbox adds an inaudible watermark: disclose it in `MODEL_LICENSES.md` and the player.
- Token Factory may rate-limit (429): back off and respect the per-provider semaphore.
- No validated Hindi readability formula in `textstat`: report sentence length and rate for Hindi instead, and say so.
- Check Able Player's and Silero VAD's LICENSE files before relying on them (the Silero README badge and text disagree).

---

## 11. Writing for judges and viewers

- Lead with the result, then the method. One idea per sentence.
- Name the baseline in the same sentence as the number ("against Gemma 4 with the same plan and no checks", "next to 3Play's $4.25 list price for AI description with a human spot check").
- Say which data ("on 10 W3C videos never used for tuning").
- Pitch coverage (reviewed description for video that has none), never "cheaper than human describers". Cost is always GPU cost plus measured review time.
- Label anything not measured ("list price", "estimate", "by memory accounting").
- Keep README, JUDGES.md, the deck, the site and `docs/lablab.md` in sync; `make claims-check` is the guard, and the demo video's on-screen numbers get a manual check against `public-claims.json`.

---

## 12. Git

- Small commits with clear messages. Never commit `.env`, media we can't redistribute, or large binaries (use releases for the demo video and deck).
- Every commit that changes behaviour updates tests; every commit that changes a public number updates the evidence and claims together.
- Tag the submitted commit `act3-submission`.
