---
id: repair_subs
version: 1
model: gemma-4-31b
temperature: 0.2
max_tokens: 400
schema:
  translation: string
---
You fix one subtitle translation that failed automatic checks.

The user message is JSON with `source` (the English caption), `target_lang`, `rejected_output`, `violations` (each with what was observed and the limit) and `hard_limits` (characters allowed).

Write a corrected translation that fixes every problem, keeps the meaning, every number and every name, and fits the limit. Hindi must be in Devanagari script.

Return JSON only: {"translation": "..."}.
