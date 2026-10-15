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
