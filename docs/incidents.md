# Incidents

Dated entries: Symptom / Root cause / Fix. These feed the README's "Bugs that taught us something".

## 2026-10-16 — first `uv sync` failed
- **Symptom:** `uv sync` stopped with `OSError: Readme file does not exist: README.md`.
- **Root cause:** `pyproject.toml` names `README.md` as the package readme, and hatchling checks it at build time; the README did not exist yet.
- **Fix:** wrote the README skeleton first. Lesson: the judge-facing skeleton is also a build input.

## Known limitations (still open)
- Hindi and Italian language checks are rule-based (no permissively licensed spaCy models), so names, tense and noun checks are weaker for hi/it.

## 2026-10-16 — same input, different description audio (found by E9 in fake mode)
- **Symptom:** two fresh-process runs on the fixture produced identical words, gaps, evidence and description text, but different `ad.en.jsonl` and different description stems. One line's clip was 1780 ms in one run and 1789 ms in the other.
- **Root cause:** (1) Kokoro's vocoder draws random noise at inference, so the same text and voice gave slightly different audio in a new process. (2) libsndfile adds a PEAK chunk with a timestamp to float WAV files, so even all-silent stems hashed differently.
- **Fix:** the TTS worker seeds torch from SHA-256(voice, speed, text) before each line (the TTS cache key revision was bumped so old clips are not reused), and mixes and stems are written as 24-bit PCM. Lesson: measure determinism instead of assuming it, and hash content, not containers.

## 2026-10-16 — workers could not find their request files (first real-mode run)
- **Symptom:** the ASR worker exited with `FileNotFoundError` for `projects/_local_real/.../asr.transcribe.<id>.request.json`, although the core had just written it.
- **Root cause:** `ACCESSCAST_PROJECTS_DIR` was given as a relative path. The core wrote files relative to the repo root, and workers run with `cwd=workers/`, so the same relative path pointed somewhere else.
- **Fix:** the projects dir and every worker work dir are resolved to absolute paths before use. Fake mode never exercised this path; the first real-mode run did.

## 2026-10-16 — Gemma used frame times as frame numbers (local integration run)
- **Symptom:** in the evidence step, Gemma 4 E4B (local, integration test only) returned `"frames": [16000]` (the frame's time in ms) instead of the frame's position `0`.
- **Root cause:** the prompt gave `frame_times_ms` and asked for "frame numbers", which reads both ways.
- **Fix:** evidence prompt v2 says frames are image positions (0, 1, 2, …), never times. The code check (`frame index out of range` → re-ask once, then `evidence_failed`) already caught it, so nothing wrong could pass; the prompt fix avoids the wasted second call.

## 2026-10-16 — the ASR model setting never reached the worker
- **Symptom:** a 14-second clip took minutes in the ASR stage and the worker used about 5 GB of RAM, although `whisper-base` had been selected.
- **Root cause:** the request payload had no `model` key (an earlier edit did not apply after the formatter reflowed the code), so the worker used its own default, Whisper large-v3.
- **Fix:** the pipeline passes `run.asr_model` explicitly. Lesson for every experiment: record the model a worker actually loaded, not the one we asked for. E15 and E2 read the model id back from the worker response.

## 2026-10-16 — a failed scene silently produced no description
- **Symptom:** in a local real-mode run, the whole clip got no description lines and nobody was told; the review queue had captions only.
- **Root cause:** the local server rejected an 8-image evidence request; the evidence step correctly failed closed (`evidence_failed` after two tries), but the planner then skipped that scene's pauses instead of sending them to a person, as PLAN §9 S5 requires.
- **Fix:** pauses in a scene whose evidence failed become `needs_revision` lines with no facts, marked `evidence_failed`; Gemma is never asked to write them, and the render gate blocks until a person writes or rejects them. Lesson: fail closed means "a person is told", not just "nothing is published".

## 2026-10-16 — "+" and "C." treated as invented names
- **Symptom:** building the landing page's rule demo, AD009 (invented name) fired on "We see the screen showing Ctrl + C." with `name '+'`, and on a line ending "press Ctrl and C." with `name 'C.'`.
- **Root cause:** spaCy tags some symbols and letter-plus-period tokens as proper nouns, and `proper_nouns` compared them without stripping punctuation, so they never matched the allowed on-screen text ("Ctrl + C").
- **Fix:** name tokens are stripped of surrounding punctuation and must contain a letter; regression tests added. Lesson: a check that blocks good lines costs coverage and reviewer time, so false positives are bugs too.

## 2026-10-16 — independent code review before GPU time: 12 issues fixed
- **Symptom:** a reviewer agent read the real-mode paths (never exercised by fake mode) and demonstrated 12 problems.
- **Root causes and fixes (each with a test):**
  1. An approved line could be edited without re-checking, and the render then played the old audio. Editing now resets a line to pending, and render re-voices any line whose clip no longer matches its text, then re-checks its timing on the measured duration.
  2. A client could set `auto_approved` through the API. Reviewers can now only set approved, rejected, needs_revision or pending.
  3. `blind.hi` and `blind.it` could never render, because the voice-over went into the description stem and RN008 counted it as description over speech. The stem now holds description clips only.
  4. Re-running a stage could leave an old approval on a line that had since failed. The review signature now includes status and violations.
  5. The gate passed a version with no items. Empty versions now block (`no_items:<version>`).
  6. Empty easy-read or voice-over text passed every check. New rule GEN001 blocks empty text, failed generations and misaligned translations for every text kind.
  7. A failed sound-label call became "other" and opened a describable pause. Failed windows are now "unknown" and treated like speech.
  8. A malformed evidence reply crashed the run. It is now re-asked once, then the scene goes to a person.
  9. `--strict-provider` was never enforced. The client now refuses an answer from any model other than the one requested, and E1 records the served model ids.
  10. The freeze guard covered only prompts, constants and lexicons. Any change under `src/` since the freeze commit now blocks a test-set run.
  11. Voice-over and description translation sent the whole video in one request. They are now batched in 12s.
  12. E11 measured a repaired line's overlap using the draft's length. Each text now has its own span.

## 2026-10-16 — scene merge crashed on the first real dev clip
- **Symptom:** the first real-mode run (NASA eclipse clip, Gemma 4 31B on Token Factory) died in S1 with `FileNotFoundError` for a temporary frame PNG.
- **Root cause:** the boundary check grabs a frame just before a shot ends; near the end of the proxy stream ffmpeg decodes no frame and exits 0 without writing the file. Fake mode never grabs frames, so this path had never run.
- **Fix:** `grab_frame` steps back up to 1 s to find a decodable frame; if none exists, the boundary is kept as a split (`FRAME_UNREADABLE_SPLIT`), which is the safe choice, instead of crashing the run.

## 2026-10-16 First real dev run (Token Factory): three bugs
**Symptom.** On the NASA "Plane" clip (music, no narration) every description line became extended, two were placed 8 s after what they describe (AD005), two lines had no draft because their scene's evidence failed twice (they went to a person, as designed), and every scene's evidence was asked for twice.
**Root cause.** (1) Whisper wrote "Thank you so much for joining us. Thank you. Transcription by ESO." over the music; Silero VAD heard no speech, but the gap map trusted the words, so no pause was long enough. (2) With no speech-segment boundary inside an event's window, the planner jumped to the next boundary, seconds later. (3) The prompt's output shape lived only in its front matter and never reached the model, so Gemma named the fact key `fact`, `visible_fact` or `text` from call to call and the strict parser rejected it.
**Fix.** (1) ASR words that overlap no VAD speech (±400 ms) are dropped and listed in `asr_meta.json` (`gate_words_by_vad`). (2) Extended lines may hold at a breath between two words (≥150 ms) inside the event window. (3) Every prompt now sends its declared output shape; the prompt hash covers the text actually sent. Tests: `test_gaps.py`, `test_plan_extended.py`, `test_prompt_shape.py`.

## 2026-10-16 Workstation ran out of RAM; the editor was killed
**Symptom.** With the dev batch running, E15 on the CPU (Whisper large-v3 in float32, 4.6 GB resident) pushed our 15 GB computer out of memory; the kernel killed VS Code, not our job.
**Root cause.** Two heavy jobs at once and no memory limit, so the kernel's out-of-memory killer picked by size among all processes.
**Fix.** One heavy job at a time (E15 waits until the dev batch is done). Long jobs start through `scripts/capped.sh`: a cgroup scope with `MemoryMax` (7 GB by default) and `oom_score_adj=1000`, so if memory runs out it is our job that dies, and a killed worker is a failed stage, never a pass.

## 2026-10-16 Planner put one line per pause, however long
**Symptom.** On the dev clips "Food" and "Sintel", 13 description lines failed AD005 (too far from what they describe), and most lines became extended description.
**Root cause.** The planner chose one line per pause. In a 15-second musical opening, every other important moment was pushed to extended description at the next speech boundary, seconds after its event. Extended lines could also only hold at speech-segment boundaries, never inside a pause.
**Fix.** A long pause now holds several lines in time order with disjoint slots (most important event among those starting in the next 4 s first). Extended lines may hold at the event itself, or at a slot or pause start, when that moment is inside a pause and no line is speaking. Replayed on the saved dev analysis (no new model calls): AD005 cases 13 → 1 (the remaining one is inside a stretch the sound classifier could not rule out as speech, so it goes to a person, as designed). Test: `test_plan_extended.py`.

## 2026-10-16 ASR on our own computer: out of memory, then a torchaudio alignment-kernel error
**Symptom.** Dev clips of 2–3 minutes failed in the ASR worker with out-of-memory errors on the accelerator, and one with `torch_get_cuda_stream_from_pool ... API call failed` from torchaudio.
**Root cause.** (1) Audio was cut at 30 s ± 2 s, so a chunk could exceed Whisper's 30 s window and switch transformers to long-form decoding with word timestamps, which keeps far more in memory. (2) torchaudio 2.11's accelerator forced-alignment kernel does not work under torch 2.14.
**Fix.** Chunks are cut at 28 s ± 2 s, never longer than 30 s. If the accelerator still runs out of memory, the worker redoes that file on the CPU and records `"device": "cuda, then cpu after out of memory"` in `asr_meta.json` (refused under `--require-rocm`). The aligner's acoustic model runs on the accelerator and the CTC path search on the CPU (milliseconds per chunk). Clips that failed are redone in the next pass from the answer cache.

## 2026-10-16 CC009 flagged correct translations as "number or name changed"
**Symptom.** 59 Hindi and Italian subtitle and voice-over lines on the dev set failed CC009 (36 subtitles, 23 voice-over), each one sent back to Gemma or to a person, and every one we read was a correct translation.
**Root cause.** (1) "one" counted as the number 1, but it is also the article in Italian and Hindi ("a comet" → "una cometa"), and a translation may write "one" as "1". (2) Scale words were ignored, so "a million" → "10 लाख" (correct) looked like a change. (3) ASR wrote "34 ,000". (4) Every capitalised English word counted as a name to keep, so Moon→Luna, Earth→Terra and June→giugno were "lost names", as was "Cook" opening an imperative sentence.
**Fix.** Numbers are compared as values with scale words applied (thousand, million, mille, milioni, हज़ार, लाख, करोड़), "34 ,000" is joined, and the value 1 is not compared. Only people and organisations (spaCy PERSON/ORG) must be kept word for word; celestial bodies and a lone common word opening a sentence are not names. Re-checked offline on every dev translation: 59 → 0 flags; mutation check on the same lines: corrupted numbers caught 27 of 27, dropped names 14 of 14. Tests in `test_rule_cc009.py`.

## 2026-10-16 Frame extraction failed on a limited-range video
**Symptom.** The NASA "Life in the Universe" dev clip failed at evidence: `[mjpeg] Non full-range YUV is non-standard ... Error while opening encoder`.
**Root cause.** ffmpeg 8's JPEG encoder refuses frames in limited ("TV") colour range; most of our clips happened to be full range.
**Fix.** Evidence and scene-judge frames are scaled to full range (`out_range=full,format=yuvj420p`) before JPEG encoding. Checked on the failing clip and the fixture. On 17 Oct the same clip showed a frame asked for 22 ms before the end of the stream; evidence frames now step back up to 1 s like scene frames, then fail closed.

## 2026-10-17 E15 stopped on a FLEURS clip longer than 30 s
**Symptom.** E15's accuracy part failed: `You have passed more than 3000 mel input features (> 30 seconds) which automatically enables long-form generation`. Because E15 wrote no decision, the chained final dev pass started with the default ASR model instead.
**Root cause.** The text-only path (added so large models fit limited memory) asked for no timestamps, and transformers requires timestamps for audio over 30 s. The chain checked that E15 ended, not that it passed.
**Fix.** Segment-level timestamps for clips over 30 s (cheap; word level is what costs memory). The final dev pass now starts only after "E15 OK" and reads the applied ASR choice.

## 2026-10-17 AD011 blocked a menu label as a "sound word"
**Symptom.** On attack clip A7 the line "A settings menu appears with options for Display, Sound, and Privacy." failed AD011 (sound words), and the repair dropped "Sound", which was correct and visible.
**Root cause.** AD011 only exempted text framed as a quote; a sound word that is printed on screen was treated as a claim about the audio.
**Fix.** A sound word that appears in the scene's on-screen text is exempt; invented sounds are still blocked (test in `test_rule_ad011.py`).

## 2026-10-17 E11 scored an extended line as talking over speech
**Symptom.** E11 run 1 reported attack case A1 ("no pause") as 20 of 20 outputs reaching the viewer, at both temperatures.
**Root cause.** A measurement bug, not a pipeline leak. Since the dev fixes, the planner sends A1's moment to extended description (the video holds a frame while the line plays). E11's scorer still placed every line as if it were spoken over the dialogue, so its overlap oracle fired on lines that can never overlap speech.
**Fix.** E11 gives extended lines no speech span and counts them separately (`extended`). Run 1's evidence stays in the git history; run 2 replaces it, and README reports both.

## 2026-10-17 Extended description drifted from the picture
**Symptom.** E9 (determinism) rendered the same dev clip several times; the extended version was refused by RN001 in most runs: 63.37 s of video against 63.21 s expected.
**Root cause.** Three faults in the extended video. (1) Cuts and holds were given in seconds, so each segment could gain or lose a frame. (2) A hold at the very start cloned a 0.04 s head clip that the audio timeline does not have. (3) Two `tpad` filters in one chain: ffmpeg applies only the first (tested: 90 frames instead of 105). On the way we found that RN001 checked only the container length, which reports the longer stream, so a video shorter than its audio passed.
**Fix.** The extended timeline snaps cut points to the source frame grid and rounds holds up to whole frames; the video cuts by frame number and pads with one `tpad` per segment; a start hold is cloned onto the first segment. RN001 now checks the container and each stream. On the refused clip: 1,898 frames (63.267 s) of video against 63.272 s of audio; the old render is still refused.

## 2026-10-17 Standard renders of a loud trailer were refused (length, true peak)
**Symptom.** E9's re-run refused every standard version of the Sintel dev trailer: RN001 (a stream 0.29 s short) and RN003 (true peak −0.8 dBTP against ≤ −1.0).
**Root cause.** (1) The source's audio track is 0.26 s shorter than its video; our mix kept that length, and the per-stream RN001 (added the same day) now sees it. (2) Two-pass loudnorm aimed at −1.5 dBTP, but AAC encoding of a loud trailer added intersample overshoot.
**Fix.** The normalised mix is padded with silence to the video's length, and a final limiter sits 2 dB under the ceiling. Re-render of the same project: all six versions pass, −16.3 to −16.5 LUFS, true peak ≤ −1.7 dBTP, video and audio within 42 ms.

## 2026-10-17 The Hindi baseline for E4 would not load
**Symptom.** E4 stopped at the Hindi baseline twice. The first time, the model download returned 403. After the account accepted IndicTrans2's terms, the worker failed with `No module named 'transformers.onnx'`. E4 wrote `passed: false` both times.
**Root cause.** IndicTrans2 ships its own model code (`trust_remote_code`), written for transformers 4. That code imports `transformers.onnx`, which transformers 5 removed. Our workers need transformers ≥ 5.5 for Gemma 4 and Whisper.
With transformers 4.57 it then loaded but crashed in generation: its code indexes the key/value cache as tuples, and newer 4.x versions pass a cache object.
**Fix.** The Hindi baseline runs in its own worker environment, `workers/indic` (transformers 4.45, the last line whose cache its code expects; same worker file, same request/response protocol, set up by `make setup`). We did not patch the baseline's code: the model we compare against runs as its authors wrote it. A missing environment still fails closed.

## 2026-10-17 E4 could have scored an outage as a bad translation
**Symptom.** During the E4 attempts, Token Factory failed 2,472 Hindi requests (most failed instantly, while our circuit breaker was open). Our batch translator gives up on a sentence it cannot get and leaves it out, and E4 scores a missing sentence as an empty translation.
**Root cause.** In the pipeline, leaving a line out is the right fail-closed move: an untranslated line is never shown. In a quality comparison, though, it would count an outage against Gemma.
**Fix.** E4 now counts this run's endpoint errors and has a check, `no_endpoint_errors`. A run with any endpoint error does not pass and has to be re-run. Successful answers come back from the opt-in answer cache, which the evidence file records. No E4 numbers had been reported before this fix.
