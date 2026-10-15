---
id: naive_caption
version: 1
model: gemma-4-31b
temperature: 0.3
max_tokens: 120
schema:
  text: string
---
Describe this video frame in one short sentence for a blind viewer, using at most {words_max} words as given in the user message.

Return JSON only: {"text": "..."}.
