# Third-party notices

AccessCast is MIT-licensed. Code reused from other projects keeps its original licence and copyright header in the file where it appears. Ideas we re-implemented in our own code are credited under "Ideas we built on".

## Code reused (with licence)

| File in AccessCast | Source | Licence | Copyright |
|---|---|---|---|
| _(filled as each file is added)_ | | | |

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
| Stage timer and benchmark.json | Katha (https://github.com/N-45div/Katha) | MIT |
| Ablation ladder with failed steps kept; incidents format | StudioMI300 (https://github.com/bladedevoff/studiomi300) | MIT |
| Alignment-safe batch translation | video-voice-translator (https://github.com/icuic/video-voice-translator) | MIT |

## Python dependencies
Installed from PyPI under their own licences (see `uv.lock`). Notable: spaCy and `en_core_web_sm` (MIT), pydantic (MIT), FastAPI (MIT), httpx (BSD-3-Clause), jiwer (Apache-2.0), wordfreq (Apache-2.0 code; data CC BY-SA 4.0), textstat (MIT), webvtt-py (MIT), PySceneDetect (BSD-3-Clause), soundfile (BSD-3-Clause).
