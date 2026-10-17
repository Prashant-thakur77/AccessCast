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
![What runs where: our computer listens; Gemma 4 31B on AMD Token Factory looks, writes, translates and repairs; code plans and checks every line; a person approves; a render gate refuses while any line waits](docs/architecture.png)

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
# What the checks caught
- **Easy-read (10 W3C test videos, never used for tuning):** Gemma alone kept every "not / never / no" in 105 of 114 captions. AccessCast published 114 of 114 with every negation kept; 7 went to a person.
- **Attack (our own attack clips):** Gemma's easy-read dropped "within 10 seconds" in 20 of 20 tries. The number check caught 20. Reached the viewer: 0.

Gemma 4 31B on AMD Token Factory.
![Easy-read captions that kept every negation: Gemma alone against AccessCast as published](docs/charts/e5_negations.png) ![Our attack cases: Gemma took the bait only on the number case, and no answer reached a viewer](docs/charts/e11_attacks.png)

---
<!-- slide: more-results -->
# More results
- **Translation (FLORES+, 1012 sentences each):** Gemma beat Opus-MT on Italian on both scores; Hindi is mixed (IndicTrans2 higher on chrF++).
- **Accessibility:** player 25 of 25 tests, review app and Studio 7 of 7, axe-core included.
![Translation: Gemma minus the baseline per language and score, with 95% intervals](docs/charts/e4_translation.png)

---
<!-- slide: amd -->
# Gemma 4 on AMD Token Factory
- Every Gemma call: **Gemma 4 31B on AMD Token Factory**, strict model check on each answer.
- From our logs: **3,162 requests** answered, **3.0 million tokens**, 28 videos (32.8 minutes).
![Gemma requests answered by AMD Token Factory, by day](docs/charts/amd_usage.png) ![Gemma tokens of one finished minute, by version](docs/charts/e14_tokens.png)

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
