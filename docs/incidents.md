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
