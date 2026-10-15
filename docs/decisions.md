# Decisions log

Every judgement call made without asking, with the date and why. Newest entries at the bottom. Cloud create/destroy events are logged here with time and cost.

---

## Start-of-work summary (16 Oct 2026, 01:45 IST)

Written after reading `PLAN.md` and `CLAUDE.md` in full and studying the reference repos in `refs/` (git-ignored).

### The five audiences (PLAN §3.1)
1. **"I can't see the screen"**: standard audio description inside the dialogue pauses (original dipped underneath), extended description that holds a frozen frame when pauses are too short, detail Brief/Standard/Detailed, and a text description track for screen readers.
2. **"I can't hear"**: SDH captions (verbatim, speaker labels on off-screen speaker change, [sound] tags). Rules only, no LLM.
3. **"Simpler words, please"**: easy-read captions (≤130 wpm, ≤12 words a sentence, one idea a sentence, digits) plus "Give me time to read".
4. **"हिन्दी"**: Hindi subtitles, Hindi voice-over in the original speech slots (original dipped, not removed), Hindi description.
5. **"Italiano"**: the same for Italian.

Profiles combine (for example, blind + Hindi).

### E1 arms and the independent overlap measure (PLAN §15.3)
- **A: Gemma 4, same plan, no checks.** Attempt 0 is published as written.
- **B: + checks.** The §10 rules run; failing lines go to a person and are counted, not rendered. No repair.
- **C: + Gemma repair.** As B, plus up to 3 repairs.
- All arms share the analysis, evidence, plan, budgets, prompts and seeds. The renderer is the same for all, and RN008 is off for all arms.
- **Independent measure:** `eval/measure_overlap.py` imports no verifier code. The speech reference is **W3C's human caption cue times**, cross-checked separately against an energy detector on the original audio (not Silero). A line "fits" if its rendered span (from the separately written description stem) overlaps no cue by more than 50 ms and ends before the next cue starts. A blind human labels invented names, unsupported claims and restated dialogue.
- **Coverage guard:** report lines published per arm, and how many W3C human-description positions have one of our lines within ±3 s. The headline is at equal coverage. If C's coverage drops more than 10 points below A's, the headline says so.
- 3 seeds with distinct `run_label`s; k/N per seed and pooled; bootstrap 95% interval clustered by video. No significance language.

### The 10 must-haves (PLAN §5)
1. One headline number that beats a named baseline, with one change between runs (E1 A→C).
2. Baselines judges respect: model-only arm A; a bigger model (E3); our own V0 ladder (E2); naive captioner (E7); strongest translation baselines (E4); W3C human description (E7); timed manual writing (E12).
3. Measured on data never used for tuning, said in those words (W3C test set, prompt freeze, `test_runs.jsonl`).
4. Every number comes from a script; estimates labelled; "by memory accounting" for GPU comparisons not run (`public-claims.json`).
5. At least one negative result published ("What didn't work").
6. AMD story in numbers: tokens/s, p95, $/1,000, users per GPU, what 192 GB fits (E13, E14, doctor, E2).
7. A live adversarial case: the model alone gets it wrong and the guard catches it in the same run (E11, `/proof`).
8. Reliability: soak, determinism, offline (E8, E9, E10).
9. Page, README and deck consistent (`make claims-check`).
10. Demo awake during judging; pitch clear to non-technical judges (static host, uptime check, plain-words script).

### Golden rules (CLAUDE.md §1, as amended today)
1. No invented numbers; `<pending: claim_id>` until measured.
2. Fail closed.
3. The model proposes, code decides; confidence is computed in code.
4. The W3C test set is never used for tuning; runs only after `make freeze-prompts`, each logged.
5. One change per experiment, against a named baseline.
6. No silent fallbacks (ROCm, provider, truncation, English).
7. Licences: reuse permissive code with headers (D-001); GemmaClip and CacheForge are ideas-only; Piper only as a CLI; no NC weights.
8. Secrets only in `.env`; no W3C-derived media committed, published or excerpted.
9. Never expose a Gemma endpoint to the internet.
10. Cloud: create and destroy the droplet ourselves if we have API access, within $100, snapshot then destroy when idle, log each event (D-002).
11. Honesty over polish.
12. Plain words.
13. Accessible by default (axe-core 0).
14. Scope is not cut to fit the schedule.

### What we reuse from the references, and where
Licences were read from each LICENSE file (not README badges).

| Source (licence) | What we reuse | Where in AccessCast | How |
|---|---|---|---|
| AudioSight (Apache-2.0, "Copyright 2026 AudioSight contributors", no NOTICE file) | `timeline.py` (insertions, `source_to_output`/`output_to_source` in integer samples); scene-merge similarity and decision logic from `clustering.py` | `media/extended.py`, `analysis/scenes.py` | Code reuse with Apache header; we add the video side (trim/tpad/concat), which AudioSight never had (its extended output is audio-only) |
| AudioSight | anchor rules, review hash binding, worker request/response protocol, fake mode, `doctor --deep` | `verify/rules_ad.py`, `review/gate.py`, `workers/`, `cli.py` | Re-implemented (code is buried in large functions); we fix its bugs listed below |
| ProteinLoop (MIT, © 2026 Anibal Perez) | repair-loop shape (`gemma_repair.py`), feedback JSON fields, health loop, docker device flags, named-checks-then-exit-1 | `repair/loop.py`, `deploy/serve_gemma.sh`, `eval/` | Code reuse where it fits, with MIT header; prompt text is ours |
| Rivet (MIT, © 2026 Enoch Idowu) | `derive_seed`, stage fingerprint, submission-check structure, benchmark pass order (warm-up, A, B, A, B), honesty table | `seeds.py`, `project.py`, `scripts/submission_check.py`, `bench/` | Code reuse with MIT header; socket guard rewritten to also cover `getaddrinfo`, `connect_ex`, `sendto` |
| PolicyCut (MIT, © 2026 PolicyCut Team; `policycut/` folder only) | store contract (`expected_revision` → 409, history JSONL, `exports_stale`), atomic write, audit builder with path sanitiser, `stage_metrics` timing, CSS variables and status colours | `review/store.py`, `review/server.py`, `bench/stage_timer.py`, review CSS | Code reuse with MIT header; the review UI itself is rebuilt for accessibility (PolicyCut's has no ARIA, a canvas-only timeline and no live region) |
| SignalForge (Apache-2.0, NOTICE "Copyright 2026 Rafael Bernucci") | JUDGES.md structure, compliance matrix, claims format, ROCm telemetry capture and summary scripts | `JUDGES.md`, `docs/compliance-matrix.md`, `bench/telemetry.py` | Structure re-implemented; telemetry scripts reused with Apache header and NOTICE |
| ageBand (Apache-2.0, no NOTICE) | "model may not return confidence" validator; `/metrics` scraping for the serving sweep | `confidence.py`, `bench/serving_sweep.py` | Reused with header; we fix its single-sample p95 and the renamed `kv_cache_usage_perc` metric |
| Katha (MIT, © 2026 N DIVIJ) | stage timer shape, Kokoro voices `hf_alpha` (lang `h`) and `if_sara` (lang `i`) | `bench/stage_timer.py`, `tts/kokoro.py` | Reused with header; we add try/finally so failed stages are recorded |
| video-voice-translator (MIT, © 2025 Video Voice Translator Contributors) | alignment-safe batch translation (numbered segments, `{id, snippet, translation}`, batch halving, single retries, snippet matcher) | `write/translate.py` | Ported to English prompts and our client, with MIT header; we never fall back to the source text (its fallback keeps English) |
| StudioMI300 (MIT per LICENSE; README badge wrongly says Apache) | ladder-table format with failed steps kept; `incidents.md` format | `docs/`, E2 | Format only |
| SayAgain (MIT) | Token Factory facts: env names, `json_object` only (no `json_schema`), 429 backoff with Retry-After | `llm/providers.py` | Re-implemented; facts recorded below |
| GemmaClip (all rights reserved) | ideas only: evidence-then-caption, frame anchors plus high-change frames, claim-ban categories, RMS silence gate | S3, S5, AD010/AD011 | Own code |
| CacheForge (no LICENSE) | ideas only: disjoint request sets per A/B arm; MI300X VF sensors read zero | E13, docs | Own code |
| Silero VAD (MIT, from LICENSE file) | VAD | S2 | Dependency. The README-badge question in PLAN §14.1 is settled: LICENSE says MIT |
| Able Player (MIT) | reference for description tracks | player | Reference; we build our own minimal accessible player first |

### What I think is wrong or risky in the plan, and how I'll handle it
1. **Schedule vs scope.** About 62 hours remain and the plan is very large. Rule 14 says don't cut scope, so the order follows the milestones, and the work that most moves the score (E1, a live site, the review gate, the AMD numbers) comes first in each milestone. Anything not finished by submission is listed in Honest Scope as not done, never claimed.
2. **TRITON_ATTN flag.** PLAN §14.2 says Gemma 4 on ROCm needs `--attention-backend TRITON_ATTN`, but ProteinLoop, the reference for that recipe, never sets it. I'll start without forcing a backend, and add the flag only if the server fails or logs say so. The result goes in `docs/incidents.md` either way.
3. **Token Factory's Gemma is unreliable for JSON.** SayAgain's catalogue (14 Oct 2026) lists `Gemma-4-31B-IT` with `json_output` but no `structured_outputs`, and its probe got degenerate output. So Token Factory gets `json_object` only, every output is validated, and failures fail closed. The droplet stays the primary endpoint for all evals.
4. **E12, E1 labels, E6 questions and native checks need people.** They are requested. Until they're done, those results stay `<pending:>` and the alternative headline rules in the pre-registration apply.
5. **Adversarial and timing-check clips need recorded people.** Decision D-003 below.
6. **W3C media download.** W3C pages embed YouTube, and the plan forbids committing the media. The fetch script will try W3C's own MP4 links first; if it has to use YouTube, it records that and keeps the files out of git.
7. **Hindi and Italian NLP.** spaCy's Italian models are not permissively licensed, and there is no Hindi model. The hi/it rules (names, tense, nouns) are rule-based and weaker. `docs/rules.md` says so per rule.
8. **AudioSight bugs we must not copy:** `ANCHOR_BEFORE_EVENT` forces description *after* the visual; `human_reviewed` comes from config, not a person; a 3.0× default `atempo`; the budget is based on scene length, not pause length; the monotonic check allows equal anchors; a filter graph that re-decodes the source once per segment.
9. **PolicyCut bugs we must not copy:** a race between the revision check and the write (we hold one lock around both); history failures swallowed; render clearing `exports_stale` without comparing revisions; `require_rocm` passing on NVIDIA (we check `torch.version.hip`).

---

## D-001 Reuse policy changed (16 Oct 2026)
The team's instruction overrides CLAUDE.md rule 7 and PLAN §21.2's "copy no code". Permissive code (MIT, Apache-2.0, BSD) may be reused directly, with headers kept, listed in `THIRD_PARTY_NOTICES.md`, plus Apache NOTICE content. GemmaClip and CacheForge stay ideas-only. Prompt text stays our own.

## D-002 Cloud policy changed (16 Oct 2026)
The team's instruction overrides CLAUDE.md rule 10. If we have API access to AMD Developer Cloud, we create and destroy the droplet ourselves, within the $100 credit; we snapshot then destroy when idle, and log each event here. **Status at 01:45 IST:** no AMD Developer Cloud token or CLI on this machine, so the team is asked to create the droplet or provide a token.

## D-003 Adversarial and timing clips are synthetic (16 Oct 2026)
PLAN §17 and §15.1 ask for team-recorded clips (with consent). To avoid filming anyone, and so the clips are ours to redistribute, we build them from Kokoro TTS voices (Apache-2.0) and generated visuals (ffmpeg drawtext, shapes, title cards). Trade-off: the E15 "hand-labelled" boundary clip uses word boundaries from the synthesizer, not a human label. Every place that uses it says "synthetic speech, synthesizer word boundaries".

## D-004 GitHub repo (16 Oct 2026)
The team supplied `github.com/Prashant-thakur77/AccessCast` (public, empty). All pushes go there; `main` is the default branch.

## D-005 Local machine has no AMD GPU (16 Oct 2026)
The development laptop has an NVIDIA RTX 3050 (6 GB). It is never used for any published number. CPU and fake mode are used for development and CI. All GPU numbers come from the MI300X droplet.

## D-006 W3C test videos fetched from YouTube with yt-dlp (16 Oct 2026)
W3C's perspective-video pages embed the videos from YouTube (`yt-id`, `yt-id-ad` in the page source) and offer no direct MP4 (HEAD requests to `media.w3.org/wai/perspective-videos/<name>.mp4` returned 404). `eval/datasets/fetch_w3c_wai.py` fetches whole videos with yt-dlp into git-ignored `data/w3c/` for private evaluation only, plus W3C's four tracks per video from `w3c/wai-website` at a pinned commit. Nothing W3C-derived is committed, published or excerpted. `export-site` refuses any project whose source hash is in the W3C manifest.

## D-007 Placeholders pass `claims-check`, fail `submission-check` (16 Oct 2026)
M1 requires `make claims-check` to pass on an empty registry, while README/JUDGES carry `<pending: id>` placeholders by design. So `claims-check` fails on wrong values, stale hashes and unregistered numbers, and only counts placeholders. `submission-check` runs it with `strict_placeholders=True`, where any placeholder fails.

## D-008 Ducking envelope computed in numpy (16 Oct 2026)
PLAN §9 S14 asks for a deterministic gain envelope via ffmpeg `volume` with an expression. We compute the same envelope (9 dB dip, 300 ms linear ramps, minimum over overlapping clips) in numpy at 48 kHz and mix there. The goal (a fixed, level-independent dip at known times) is unchanged. It avoids very long ffmpeg expressions for videos with many lines, and it is unit-testable. Loudness is still two-pass ffmpeg `loudnorm` with `I` set explicitly.

## D-009 Whisper word probabilities not extracted (16 Oct 2026)
The transformers ASR pipeline's word timestamps do not include per-word probabilities. Rather than run a second decoding pass, `prob` is recorded as 1.0, and ASR uncertainty in confidence comes from the independent Gemma E4B cross-check (S2b, ×0.8 on disagreement). Confidence weights are still set on the dev set only.

## D-010 Minimum useful budget of 3 words (16 Oct 2026)
On the fixture, a 1.48 s opening pause got a 2-word budget, and "repair" produced the useless "White text". A pause too short for 3 words is no longer used for standard description, and its important facts become extended-description candidates. `AD_MIN_USEFUL_WORDS = 3` in `constants.py` (dev-tuned).

## D-011 Extended-description insertion point (16 Oct 2026)
PLAN §9 S6 says "at the next end of a speech segment". On the fixture, that put the opening title's description 4 s after the title, outside AD005's window. Insertions now go at the speech boundary nearest the event (start of video, start or end of a speech segment, never inside a word) within the AD005 window. They fall back to the next boundary, where AD005 sends them to a person.

## D-012 Voice-over and subtitle slots may use following silence (16 Oct 2026)
Hindi voice-over is often longer than the English speech. A voice-over slot runs from the speech start to the next speech minus 200 ms, at most 1.5 s past the original speech end (`VO_TAIL_MS`, `VO_GAP_BEFORE_NEXT_MS`). Subtitles extend into following silence before CC001 judges speed, as SDH already does (PLAN §9 S10). VO001's 1.15× tempo cap is unchanged.

## D-013 AD006 compares a sibling only within its own slot (16 Oct 2026)
During parallel verification, a sibling line's length was estimated from its unrepaired draft, which made a valid line fail AD006 three times. AD001 already keeps every standard line inside its own pause, so a sibling's span is capped at its slot end when checking for overlap.

## D-014 Development set (16 Oct 2026)
Six NASA Goddard explainers (eclipse ×2, comet, exoplanets, a Worldview screen tutorial with on-screen text, a climate-scientist interview), three Prelinger public-domain films (TV commercials, operator dialling, pedestrian safety), the Sintel trailer and a Big Buck Bunny excerpt. Long clips are trimmed to their first 180 s (120 s for BBB) to save GPU time; dev clips may be cut. The 20 s synthetic fixture and the synthetic adversarial clips (D-003) are also dev data.

## D-015 Scene length clamp splits evenly (16 Oct 2026)
PLAN §9 S1 says scenes longer than 45 s split "at the largest visual change". The first implementation splits them evenly into ≤ 45 s parts. Revisit if dev clips show splits landing mid-action.
