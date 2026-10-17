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
The development computer has no AMD GPU. CPU and fake mode are used for development and CI. Amended by D-021: with no droplet, Gemma 4 31B runs on AMD Token Factory and the non-Gemma helper models run on our own computer; no number from our own computer is ever presented as an AMD measurement.

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

## D-016 Local integration runs with Gemma 4 E4B on Ollama (16 Oct 2026)
Without the droplet, real-mode runs (not fake mode) use Ollama 0.33.2 serving `gemma4:e4b` on our own computer through its OpenAI-compatible API, with `whisper-base` on CPU. Purpose: catch integration bugs (request shapes, JSON handling, worker paths, prompt ambiguities) before GPU time is spent. These runs are never evidence: they use a different model size and server, and their outputs stay in git-ignored `projects/_local_real/`. They already found three bugs (relative worker paths, frame times used as frame numbers, and the ASR model setting not reaching the worker; see `docs/incidents.md`).

## D-017 W3C DAPT export is best effort (16 Oct 2026)
`render` writes W3C DAPT TTML scripts (`asRecorded` description, `originalTranscript`, `translatedTranscript`) into `render/dapt/`. DAPT is a Candidate Recommendation Draft; we validate well-formedness only and say so. It is a P2 extra for broadcasters, not a claim of conformance.

## D-018 Outside facts verified; two corrections (16 Oct 2026)
A fact check of every outside number (`evidence/cited_claims.json`, 49 verified with word-for-word quotes, 9 unverified and therefore not used) corrected the plan in two places. GBD 2019 / Lancet Global Health gives 43.3 million blind people, not 43.9 million; PLAN.md is fixed. DigitalOcean's AMD Developer Cloud page now lists the MI300X at $2.59 per hour, not $1.99, so `GPU_HOURLY_COST_USD` defaults to 2.59 (cited) and will be set to the rate actually billed when the droplet is created; every cost number names the rate it used. Facts read only from a secondary source or mirror (3Play's restatement of Ofcom's 80% figure, Tubefilter for YouTube uploads, a EUR-Lex mirror for the EAA wording, Ireland's CSO page for the OECD data) carry a `note` and must say so where used.

## D-019 Hindi and Italian voices: Kokoro by default, Chatterbox as an option (16 Oct 2026)
Chatterbox Multilingual (MIT) is integrated as a selectable engine for hi/it in its own worker env (it pins torch 2.6). On CPU it was slow (15.9 s for 2.44 s of Hindi) and logged "forcing EOS token" on a Hindi line, which can mean the line was cut short. Kokoro (`hf_alpha`, `if_sara`, `hm_omega`, `im_nicola`) stays the default until two measurements exist: time per second of audio on the MI300X, and a native Hindi and Italian speaker's rating of the same lines in both voices. A forced end of sentence is flagged `tts_eos_forced` on the line, so a reviewer always hears it. Chatterbox's Perth watermark is disclosed in the player whenever its clips are used.

## D-020 Site redesign with dontboardme.com as the reference (16 Oct 2026)
On the team's request, the public site was redesigned using https://dontboardme.com/ as the only reference and inspiration. All of its pages were screenshotted at desktop and mobile widths and studied. We took patterns, not assets: giant condensed type against tiny captions, a colour world per section, rotating circle text, discs and half-circle edges, pill buttons, an orbit for "How it works?", and big result rows. No code, images, fonts or copy were copied; our fonts are OFL (Anton, Inter, Noto Sans Devanagari), and the palette is our own (`docs/design/brief.md`). Their site blocks entry until you bounce a ball. Ours never blocks: the hero's "Close your eyes" listening toggle is optional. Everything works by keyboard and with reduced motion, and E16 was re-run on the new site (player 22 of 22 tests, review app 5 of 5, axe-core included). The player moved to `watch.html`; old `?audience=` and `?p=` links redirect there.

## D-021 No MI300X droplet: Gemma 4 31B on AMD Token Factory; other models on our workstation (16 Oct 2026)
AMD Developer Cloud needs a payment card on file before a GPU droplet can be created, even with credits, and the team has no card the console accepts. So no droplet will be created, and nothing below claims MI300X numbers we did not measure.
- **Gemma 4 31B** (evidence, writing, repair, captions, easy-read, translation, scene judgments) runs on **AMD Token Factory** (`Gemma-4-31B-IT`, OpenAI-compatible, `--strict-provider`; the served id is recorded on every call). Token Factory publishes no hardware details we could cite, so we say "AMD Token Factory" and never "on an MI300X".
- **Whisper, the wav2vec2 aligner, Silero VAD, Kokoro and the metric models** are not Gemma. They run on our own computer; whether a worker used the CPU or an accelerator is written in its response (`device`) and in every evidence file (`environment.worker_device`). Public text says "our own computer" and never presents this work as AMD.
- **Gemma 4 E4B (audio)** is not offered by Token Factory. The ASR cross-check (S2b) and sound labels (S3) run in the explicit `ACCESSCAST_AUDIO_MODEL=none` mode: recorded as "not run" in every project, so captions carry no sound labels and gaps fall back to Whisper words plus Silero VAD.
- **Not run, and said so:** E2 (speed ladder), E8 (soak), E10 (offline run), the memory table, and E14's GPU dollars, because each measures our own MI300X server. E13 is re-scoped to client-side latency and throughput against Token Factory, labelled as such. E14 reports Gemma tokens per finished minute instead of GPU dollars.
- `deploy/` and `run_session.sh` stay in the repo unchanged, so anyone with a droplet can run the MI300X experiments.

## D-022 Sound labels from AST instead of Gemma 4 E4B (16 Oct 2026)
Without E4B (D-021) the captions for deaf and hard-of-hearing viewers would carry no sound labels. Sound windows are now labelled by the Audio Spectrogram Transformer fine-tuned on AudioSet (`MIT/ast-finetuned-audioset-10-10-0.4593`, BSD-3-Clause) on our workstation, with `ACCESSCAST_SOUND_MODEL=ast`. AudioSet classes map to our closed vocabulary in `constants.AUDIOSET_TO_VOCAB`; any speech-like class at or above the threshold becomes `unknown` and any singing becomes `music_with_lyrics`, both treated as speech by the gap map (fail closed). `sounds.json` names the model. Public text says sounds are labelled by a non-Gemma audio classifier.

## D-023 Backup Gemma source: Google AI Studio, whole experiments only (16 Oct 2026)
Token Factory's Gemma-4-31B-IT answered HTTP 500/503 "no available workers" for most of the evening of 16 Oct. To keep the deadline, the client can also reach `gemma-4-31b-it` on Google AI Studio (`--provider aistudio`, key in `GEMINI_API_KEY`, no card needed). It is the same model family and size, served by Google, not AMD. Rules: Token Factory stays the default; an experiment uses exactly one provider from start to finish (strict provider check on every call, provider recorded in its config); any public number from an AI Studio run says "Gemma 4 31B on Google AI Studio" in the same sentence. Gemma there takes no system role and no JSON mode, so the instructions go first in the user turn and the reply is parsed and checked as usual.

## D-024 Voice timing refitted on dev description lines; word budget keeps a margin (16 Oct 2026)
The first `af_heart` calibration came from generated plain-word sentences and under-predicted real description lines (median 0.26 s short, 95th percentile 1.5 s), so Gemma's lines stayed inside their word limit and still overran their pause (AD001 fired 25 times on dev drafts). `scripts/calibrate_from_dev.py` refits seconds = intercept + s_per_word × words on the 183 voiced dev description lines (16 videos; dev data only), and the planner subtracts `AD_BUDGET_MARGIN_S` = 0.23 s (the 75th percentile of the remaining error) from every pause before turning it into words. Replayed on the saved dev analysis: more moments become extended description where a pause cannot fit a useful line, and placement stays within each event's window. Decided before the test freeze.

## D-025 E15 chooses only among ASR setups that run on our computer (17 Oct 2026)
Whisper large-v3 with word timestamps does not fit our computer: on the accelerator it runs out of memory, and the CPU redo passed the 7 GB memory cap and was killed (twice, 16–17 Oct). The gap map needs word timings, so a model that cannot produce them here cannot be the timing source. E15 still measures every model's accuracy on FLEURS (dev) and reports it; the word-boundary part and the decision consider only setups that produced word timings, and the evidence file lists the others under `not_candidates` with the reason. Part-1 transcripts are saved so a crash does not repeat them. Decided before the test freeze, on dev data only.

## D-026 E1 is a negative result; the headline waits for E12 (17 Oct 2026)
E1 ran once under test-freeze-1 (10 W3C videos × 3 seeds, Gemma 4 31B on AMD Token Factory, no endpoint errors). The test videos have 6 usable pauses (10.5 s in 9.3 min; 5 of 10 videos have none), so only 6 standard lines were planned and arms A and C came out equal. Pre-registered rule 4 applies: E1 goes to "What didn't work" with its numbers, and the headline moves to E12, then E6, then E3. E6 can no longer be run validly (its questions had to be written before the first test run), and E3 needs our own server. So the headline is E12 if the two-person timing study is done; we did not re-tune or re-run E1 to rescue it. E7 shares E1's lines and is equally uninformative (3 of 82 human cues paired); E5 and E11 are reported as measured, not promoted to the headline after the fact.

## D-027 Headline without a comparison until E12 runs (17 Oct 2026)
With E1 negative, E6 invalid and E3 impossible (D-026), and E12 not yet done, README line 1, the deck title and the lablab short description say what AccessCast does, with no comparative number: "One video, five versions: AccessCast uses Gemma 4 31B on AMD Token Factory to write audio description, captions, easy-read, Hindi and Italian versions, checks every line in code, and a person approves what the public hears." E5 and E11 stay in the results, not the headline, as pre-registered. If E12 is measured before submission, its result becomes the headline. Wording updated the same day to lead with the viewers (lablab's guide: the value must be clear from the first screen): "Blind, deaf, slow-reading, Hindi and Italian viewers each get their own version of the same video: Gemma 4 on AMD writes it, code checks every line, and a person approves it before anyone hears it."

## D-028 The live attack runs as a Vercel function (17 Oct 2026)
No droplet, and Hugging Face now charges for Docker Spaces, so the proof API runs as a Python function in the same Vercel project as the site (`site/api/attack.py`, built by `scripts/build_vercel_api.sh`). Its dependencies are pruned to fit Vercel's limit (spaCy and its small English model, word-frequency data for English, Hindi and Italian only, no tests, stripped binaries; 160 MB) and were checked to give the same results as the full environment (no check crashes; the number check blocks the same answers). It runs only the fixed easy-read case A5 (the case with the highest measured failure rate in E11), five tries per press, in parallel, against Gemma 4 31B on AMD Token Factory. The key is in Vercel's environment settings only. The oracle is E11's, inlined and tested for parity (`tests/unit/test_proof_oracle.py`). If the endpoint fails, the page says so and shows the recorded run.

## D-029 (18 Oct 2026): Spanish, French and Portuguese (Brazil)
**Why.** Viewers and buyers: Spanish has the largest non-English share of Netflix viewing (Netflix, H2 2023), Brazil's
ANCINE rule asks for subtitles and audio description in cinemas, and French is an EU accessibility market. Kokoro has
voices for all three (Apache-2.0). **What.** Subtitles and voice-over for es, fr and pt, with the same checks (number,
name, untranslated, reading speed at Netflix's 17 characters per second for each); translated description stays Hindi
and Italian. **Measurement.** Adding the languages edits the translation prompt's language list, so its hash changes:
E4's Hindi and Italian results were measured with the earlier text. Spanish, French and Portuguese get their own E4
run (FLORES+ devtest against Opus-MT); until it runs, no quality number is stated for them.

