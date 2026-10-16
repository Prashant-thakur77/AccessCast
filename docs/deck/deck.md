<!-- slide: title -->
# AccessCast
## One video. Five ways to watch.
<pending: e1.headline>

Gemma 4 on AMD Token Factory · AMD Developer Hackathon ACT III · Create a New Kind of Experience

---
<!-- slide: problem -->
# Most video says nothing to people who can't see it
- 43.3 million people are blind and 295 million have moderate to severe vision loss.
- 430 million people need rehabilitation for disabling hearing loss.
- 26% of adults read at or below the lowest literacy level.
- The largest free archive of described video holds about 310 hours hours. YouTube received 500 hours hours a minute.

---
<!-- slide: law -->
# The law already asks for it
| Where | Rule | When |
|---|---|---|
| EU | European Accessibility Act | 28 June 2025 |
| Italy | D.Lgs. 82/2022, fines €5,000 to €40,000 | in force |
| India | MIB accessibility guidelines for OTT | 6 February 2026 |
| US | ADA Title II web rule (WCAG 2.1 AA) | 26 April 2027 |

---
<!-- slide: product -->
# One video, five experiences
"I can't see the screen" · "I can't hear" · "Simpler words, please" · "हिन्दी" · "Italiano"

All five are built from one analysis, so they never disagree. Profiles combine.

---
<!-- slide: how -->
# How it works
1. Listen: Whisper words, forced alignment, Gemma 4 E4B cross-checks the transcript and labels sounds.
2. Look: Gemma 4 31B lists what is visible, at temperature 0.
3. Plan: code finds the pauses and gives each line a word budget.
4. Write: Gemma writes only from the visible facts.
5. Check: code checks every line. Gemma repairs. A person approves.
6. Render: one MP4 per audience, loudness and timing checked.

---
<!-- slide: quality -->
# The model proposes, code decides
- Rules tied to the real audio timeline: the line must fit the pause, measured in milliseconds.
- Names, claims, sounds, restated dialogue and injected instructions are blocked in code.
- Confidence is computed from measurements, never asked of the model.
- The server refuses to render while any line waits for a person.

---
<!-- slide: headline -->
# What the checks caught (test set)
- **Easy-read:** Gemma alone kept every "not / never / no" in 104 of 115 captions. AccessCast published 115 of 115 with every negation kept; 6 went to a person.
- **Live attack:** Gemma's easy-read dropped "within 10 seconds" in 20 of 20 tries. The number check caught 20. Reached the viewer: 0.

Test set: 10 W3C videos never used for tuning. Gemma 4 31B on AMD Token Factory.

---
<!-- slide: more-results -->
# More results
<!-- results.more:start -->
- **Speech recognition (E15, dev set).** We chose Whisper large-v3-turbo: its English word error rate was 4.5% on 100 FLEURS clips, against 4.3% for the larger large-v3 (Hindi 32.4%, Italian 3.0%). After forced alignment, word boundaries were off by 54 ms at the median and 339 ms at the 95th percentile (raw Whisper: 480 ms), on 224 word boundaries of our synthetic clips, so description keeps 340 ms clear of speech. Large-v3 could not produce word timings within our computer's memory, so it was not a candidate.
- **Easy-read (E5, 10 W3C videos never used for tuning).** Asked to simplify the captions, Gemma alone kept every "not", "never" and "no" in 104 of 115 cues; in the others the sentence lost its negation and so its meaning. The easy-read AccessCast published kept them in 115 of 115, and sent 6 of 121 cues to a person instead. Paced for slow reading (at most 130 words a minute): 106 of 115 published cues, against 57 of 121 original captions. These counts use a negation counter close to our own check, so a blind rating by people leads this experiment; it is still to come.
- **Accessibility (E16).** Automatic tests with keyboard-only runs and axe-core scans pass: player 23 of 23, review app and Studio 6 of 6. No blind tester has used it yet.
<!-- results.more:end -->

---
<!-- slide: amd -->
# Gemma 4 on AMD Token Factory
- Every Gemma call: **Gemma 4 31B on AMD Token Factory**, strict model check on each answer.
- Measured from our side: 17 generated tokens/s at the best concurrency, p95 13.9 s; 15 of 120 requests refused by our key's rate limit.
- Cost basis: 41,818 Gemma tokens per finished minute, all five versions (dev set).
- Whisper, the voices and the sound classifier run on our own computer. No MI300X numbers: we had no droplet.

---
<!-- slide: reliability -->
# It holds up
- Live attacks: 0 outputs reached a viewer, over 8 cases × 40 tries.
- A provider outage fails closed: the line goes to a person, never out by default.
- Accessibility tests pass: player 23 of 23, review app and Studio 6 of 6.

---
<!-- slide: business -->
# Who pays, and what it costs
- European Accessibility Act applies from 28 June 2025; Italy's fines €5,000 to €40,000.
- India's OTT accessibility guidelines: 6 February 2026. US ADA Title II, large public bodies: 26 April 2027.
- List prices today: $4.25 a minute for AI description with a human spot check (3Play Media); $6.65–$14.70 for human description (University of Michigan).
- Our cost: 41,818 Gemma tokens per finished minute, plus a person's review time (E12).

---
<!-- slide: honest -->
# What didn't work, and what's next
- **E1 did not work on our test set:** the W3C videos have 6 usable pauses in 9.3 minutes, so only 6 standard lines were planned and the arms came out equal.
- Gemma never failed 6 of our 8 attack cases, so those checks were not exercised live.
- Hindi speech recognition is weak: 32.4% word error rate.
- Token Factory dropped requests for long stretches; everything fails closed, but it slows the work.
- Not yet: a blind reviewer, native-speaker checks, MI300X numbers.

Prior work: AudioSight, ViddyScribe, AutoAD-Zero. Code: github.com/Prashant-thakur77/AccessCast · Live: accesscast.vercel.app
