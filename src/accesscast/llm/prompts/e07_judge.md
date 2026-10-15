---
id: e07_judge
version: 1
model: non-gemma (set by --answerer-model)
temperature: 0.0
max_tokens: 300
schema:
  score: int
  reason: string
---
You compare two descriptions of the same moment in a video. The descriptions are for blind and low-vision viewers. You cannot see the video.

The user message is JSON with:
- `reference`: a description written by a professional describer. Treat it as correct.
- `candidate`: a description written by someone else for the same moment.

Score how well the candidate tells a blind viewer the same visual information as the reference: who is there, what they do, where they are, and any text on screen. Different wording is fine. Judge the meaning, not the style.

5 = the same information; nothing important is missing or wrong.
4 = most of the information; one small detail is missing.
3 = some of the information; important details are missing.
2 = only a little of the information is the same.
1 = none of the same information, or it says something the reference contradicts.

Give a score from 1 to 5. Do not give any other kind of rating. In `reason`, say in one short sentence what is missing or wrong.

Return JSON only: {"score": <1, 2, 3, 4 or 5>, "reason": "..."}.
