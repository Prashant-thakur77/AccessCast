# Incidents

Dated entries: Symptom / Root cause / Fix. These feed the README's "Bugs that taught us something".

## 2026-10-16 — first `uv sync` failed
- **Symptom:** `uv sync` stopped with `OSError: Readme file does not exist: README.md`.
- **Root cause:** `pyproject.toml` names `README.md` as the package readme, and hatchling checks it at build time; the README did not exist yet.
- **Fix:** wrote the README skeleton first. Lesson: the judge-facing skeleton is also a build input.

## Known limitations (still open)
- Hindi and Italian language checks are rule-based (no permissively licensed spaCy models), so names, tense and noun checks are weaker for hi/it.
