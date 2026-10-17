<!-- slide: title -->
# AccessCast
## One video. Five ways to watch.
Blind, deaf, slow-reading, Hindi and Italian viewers each get their own version of the same video: Gemma 4 on AMD writes it, code checks every line, and a person approves it before anyone hears it.

Gemma 4 on AMD Token Factory · AMD Developer Hackathon ACT III · Create a New Kind of Experience

---
<!-- slide: problem -->
# Most video says nothing to people who can't see it
- 43.3 million people are blind and 295 million have moderate to severe vision loss.
- 430 million people need rehabilitation for disabling hearing loss.
- 26% of adults read at or below the lowest literacy level.
- The largest free archive of described video holds about 310 hours. YouTube received 500 hours a minute.

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
1. Listen: Whisper finds every word and pause, forced alignment times them, and a small audio classifier labels the sounds between words.
2. Look: Gemma 4 31B lists what is visible, at temperature 0.
3. Plan: code finds the pauses and gives each line a word budget.
4. Write: Gemma writes only from the visible facts.
5. Check: code checks every line. Gemma repairs. A person approves.
6. Render: one MP4 per audience, loudness and timing checked.

---
<!-- slide: demo -->
# See it working
![AccessCast Studio after a real run: every step done, 29 Gemma calls answered, lines per version waiting for review](docs/media/studio.png) ![The proof page: Gemma dropped the time limit in 20 of 20 tries, our checks blocked all 20, and Gemma's repair put it back](docs/media/proof.png)

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
- **Easy-read:** Gemma alone kept every "not / never / no" in 105 of 114 captions. AccessCast published 114 of 114 with every negation kept; 7 went to a person.
- **Live attack:** Gemma's easy-read dropped "within 10 seconds" in 20 of 20 tries. The number check caught 20. Reached the viewer: 0.

Test set: 10 W3C videos never used for tuning. Gemma 4 31B on AMD Token Factory.

---
<!-- slide: more-results -->
# More results
- **Speech recognition (dev):** Whisper large-v3-turbo, 4.5% English word error rate; word timing off by 54 ms (median) after alignment.
- **Easy-read (test):** published cues paced for slow reading: 106 of 114, against 57 of 121 original captions.
- **Translation (FLORES+, 1012 sentences each):** Italian: Gemma beat Opus-MT on both scores (COMET 0.8898 against 0.8522). Hindi: Gemma higher on COMET, IndicTrans2 higher on chrF++.
- **Accessibility:** player 25 of 25 tests, review app and Studio 7 of 7, axe-core included.

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
- Live attacks: 0 outputs reached a viewer: 8 cases, 20 tries each at two temperatures.
- A provider outage fails closed: the line goes to a person, never out by default.
- Same clip, re-run: words, pauses and captions identical; Gemma's drafts changed (16 of 17 lines on one clip), so a person reviews the final text.
- Accessibility tests pass: player 25 of 25, review app and Studio 7 of 7.

---
<!-- slide: business -->
# Who pays, and what it costs
- European Accessibility Act applies from 28 June 2025; Italy's fines €5,000 to €40,000.
- India's OTT accessibility guidelines: 6 February 2026. US ADA Title II, large public bodies: 26 April 2027.
- List prices today: $4.25 a minute for AI description with a human spot check (3Play Media); $6.65–$14.70 for human description (University of Michigan).
- Our cost: 41,818 Gemma tokens per finished minute, plus a person's review time (E12).

---
<!-- slide: sold -->
# How it is sold
- **First customer:** a US public university's accessibility office: ADA Title II from 26 April 2027, years of video with no description.
- **They buy:** all five versions per finished minute, below today's AI-description list prices, reviewed by their own staff in our app; or a yearly licence to run it on their own servers.
- **Next:** broadcasters and streaming platforms in the EU, Italy and India.
- **The difference:** five audiences from one analysis, checks that catch meaning changes, and a server that refuses to publish unreviewed lines.

---
<!-- slide: honest -->
# What didn't work, and what's next
- **E1 did not work on our test set:** the W3C videos have 6 usable pauses in 9.3 minutes, so only 6 standard lines were planned and the arms came out equal.
- Gemma never failed 6 of our 8 attack cases, so those checks were not exercised live.
- Hindi translation: IndicTrans2 beat Gemma on chrF++ (58.8 against 53.8).
- Hindi speech recognition is weak: 32.4% word error rate.
- Token Factory dropped requests for long stretches; everything fails closed, but it slows the work.
- Not yet: a blind reviewer, native-speaker checks, MI300X numbers.

Prior work: AudioSight, ViddyScribe, AutoAD-Zero. Code: github.com/Prashant-thakur77/AccessCast · Live: accesscast.vercel.app
