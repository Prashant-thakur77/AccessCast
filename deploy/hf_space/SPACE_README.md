---
title: AccessCast proof API
emoji: 🛡️
colorFrom: indigo
colorTo: red
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Live attack test for AccessCast (Gemma 4 31B on AMD Token Factory)
---

The API behind "Run the attack" on https://accesscast.vercel.app/proof.html. It runs fixed attack cases only (no
free-form prompts) against Gemma 4 31B on AMD Token Factory, a fresh seed per try, and reports what Gemma wrote,
which checks blocked it and whether anything reached the viewer. Rate-limited per IP. Code:
https://github.com/Prashant-thakur77/AccessCast (MIT).
