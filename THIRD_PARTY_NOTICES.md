# Third-party notices

AccessCast is MIT-licensed. Code reused from other projects keeps its original licence and copyright header in the file where it appears. Ideas we re-implemented in our own code are credited under "Ideas we built on".

## Code reused (with licence)

| File in AccessCast | Source | Licence | Copyright | What we took |
|---|---|---|---|---|
| `src/accesscast/media/timeline.py` | AudioSight `src/audiosight/timeline.py` (commit 5c708f6) | Apache-2.0 | 2026 AudioSight contributors | copied with header; sample rate changed to 48 kHz; `remap_ms` added |
| `src/accesscast/analysis/scenes.py` | AudioSight `src/audiosight/clustering.py` | Apache-2.0 | 2026 AudioSight contributors | similarity formula and decision thresholds, rewritten with PIL/numpy |
| `src/accesscast/seeds.py` | Rivet `rivet/pipeline/seeds.py` | MIT | (c) 2026 Enoch Idowu | `derive_seed` |
| `src/accesscast/guard/network.py` | Rivet `rivet/telemetry/network_guard.py` | MIT | (c) 2026 Enoch Idowu | idea, rewritten and extended (getaddrinfo, connect_ex, sendto) |
| `scripts/submission_check.py` | Rivet `cli/submission_command.py` | MIT | (c) 2026 Enoch Idowu | structure of the checks |
| `src/accesscast/repair/loop.py` | ProteinLoop `sim/proteinloop_sim/gemma_repair.py` | MIT | (c) 2026 Anibal Perez | loop shape and stop reasons |
| `deploy/serve_gemma.sh` | ProteinLoop `scripts/amd_notebook_setup_vllm.sh` | MIT | (c) 2026 Anibal Perez | health-loop shape |
| `src/accesscast/review/store.py` | PolicyCut `policycut/api/events.py`, `policycut/core/storage.py` | MIT | (c) 2026 PolicyCut Team | store contract, rewritten (single lock, no swallowed history errors) |
| `workers/common.py` (`stage_timer`) | PolicyCut `policycut/core/device.py` `stage_metrics` | MIT | (c) 2026 PolicyCut Team | synchronized GPU timing shape |
| `src/accesscast/write/text_versions.py` (`translate_batch`) | video-voice-translator `src/text_translator.py` | MIT | (c) 2025 Video Voice Translator Contributors | alignment-safe batch translation, rewritten with English prompts and fail-closed behaviour |
| `workers/tts_worker.py` (voice map) | Katha `katha/config.py` | MIT | (c) 2026 N DIVIJ | Kokoro language codes and hi/it voice ids |
| `src/accesscast/confidence.py` (`reject_model_confidence`) | ageBand `src/contracts/validators.py` | Apache-2.0 | ageBand authors | pattern only, our own code and formula |
| `eval/e13_serving.py` | ageBand `scripts/benchmark_roster.py` | Apache-2.0 | ageBand authors | `/metrics` delta method, rewritten (full request sets, warm-up, repeats) |

### AudioSight NOTICE
AudioSight ships no NOTICE file. Its licence appendix reads "Copyright 2026 AudioSight contributors", which is kept in the header of each file above that contains its code.

### Apache-2.0 NOTICE content carried from upstream
- SignalForge — NOTICE: "Copyright 2026 Rafael Bernucci" (carried if any SignalForge code is reused)

## Ideas we built on (re-implemented, no code copied)

| Idea | From | Licence of source |
|---|---|---|
| Evidence first, then the caption; frame anchors plus high-change frames; claim types to forbid; RMS silence gate | GemmaClip (https://github.com/ArmmyC/GemmaClip) | All rights reserved — ideas only |
| One setting changed per A/B arm; disjoint request sets; MI300X virtual-function sensors read zero | CacheForge (https://github.com/lucheeseng827/amd-hackathon) | No licence file — ideas only |
| Scene merge, anchor rules, expanded timeline, review bound to a hash | AudioSight (https://github.com/austin1997/AudioSight) | Apache-2.0 |
| Verifier → feedback → Gemma repair, never promote a failure | ProteinLoop (https://github.com/Anarpego/ProteinLoop) | MIT |
| Audit gate with observed vs threshold, offline guard, honesty table | Rivet (https://github.com/damishafe/Rivet) | MIT |
| Review UI contract and server-side render gate | PolicyCut (https://github.com/xiaodouzi666/Radeon-hackathon-2026-07/tree/main/policycut) | MIT |
| JUDGES.md, compliance matrix, claims registry | SignalForge (https://github.com/rvbernucci/signalforge) | Apache-2.0 |
| Confidence computed in code; serving sweep method | ageBand (https://github.com/asishbose/ageBand) | Apache-2.0 |
| Site look and feel: condensed display type with tiny captions, colour per section, rotating circle text, discs, orbit layout (patterns only; no code, images, fonts or copy) | dontboardme.com (https://dontboardme.com/), design by thefirstthelast.agency | design inspiration only |
| Stage timer and benchmark.json | Katha (https://github.com/N-45div/Katha) | MIT |
| Ablation ladder with failed steps kept; incidents format | StudioMI300 (https://github.com/bladedevoff/studiomi300) | MIT |
| Alignment-safe batch translation | video-voice-translator (https://github.com/icuic/video-voice-translator) | MIT |

## Python dependencies
Installed from PyPI under their own licences (see `uv.lock`). Notable: spaCy and `en_core_web_sm` (MIT), pydantic (MIT), FastAPI (MIT), httpx (BSD-3-Clause), jiwer (Apache-2.0), wordfreq (Apache-2.0 code; data CC BY-SA 4.0), textstat (MIT), webvtt-py (MIT), PySceneDetect (BSD-3-Clause), soundfile (BSD-3-Clause), pyannote.audio (MIT, diarization worker env `workers/diarize`).
