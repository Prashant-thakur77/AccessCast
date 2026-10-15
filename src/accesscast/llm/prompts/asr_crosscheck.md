---
id: asr_crosscheck
version: 1
model: gemma-4-e4b
temperature: 0.0
max_tokens: 600
schema:
  text: string
---
Transcribe the following speech segment in {LANGUAGE} into {LANGUAGE} text. The user message names the language.

Return JSON only: {"text": "..."}. If there is no speech, return {"text": ""}.
