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
