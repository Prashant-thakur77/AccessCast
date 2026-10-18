<!-- slide: title -->
# AccessCast
## One video. Made for every viewer.
Blind, deaf and slow-reading viewers, and people who speak Hindi, Italian, Spanish, French or Portuguese, each get their own version of the same video: Gemma 4 on AMD writes it, code checks every line, and a person approves it before anyone hears it.

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
# One video, every viewer
"I can't see the screen" · "I can't hear" · "Simpler words, please" · "हिन्दी" · "Italiano" · "Español" · "Français" · "Português"

Every version is built from one analysis, so they never disagree. A viewer can combine them: description in Hindi, say.
![The viewer picker on our site: I can't see the screen, I can't hear, simpler words, and five languages](docs/media/picker.png)

---
<!-- slide: how -->
# How it works
![What runs where: our computer listens; Gemma 4 31B on AMD Token Factory looks, writes, translates and repairs; code plans and checks every line; a person approves; a render gate refuses while any line waits](docs/architecture.png)

---
<!-- slide: demo -->
# See it working, live on AMD
On the live site, Gemma 4 31B on AMD Token Factory writes while you watch, and our checks test every line: **run the attack**, **try your own caption**, or **describe your own picture**. Nothing you type or upload is stored.
![The Try box: one sentence in easy-read and five languages; the number check stopped the Italian, French and Portuguese lines and Gemma's repairs passed](docs/media/try.png) ![How it works on a real clip: rule AD011 stopped the draft "speaks to the camera", and Gemma's repair passed every check](docs/media/how.png)

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
- **Translation (FLORES+, 1012 sentences each):** Gemma higher than the specialist model on COMET in all five languages; on chrF++ higher for Italian, no clear difference for Spanish, lower for Hindi, French and Portuguese.
- **Every language, same checks (2 site drafts):** lines that passed on their own: Hindi 74 of 81, Italian 74 of 81, Spanish 73 of 81, French 70 of 81, Portuguese 76 of 81. The rest wait for a person.
![Translation: Gemma minus the baseline per language and score, with 95% intervals](docs/charts/e4_translation.png) ![Lines per language that passed every check](docs/charts/e18_languages.png)

---
<!-- slide: amd -->
# Gemma 4 on AMD Token Factory
- Every Gemma call: **Gemma 4 31B on AMD Token Factory**, strict model check on each answer.
- From our logs: **3,730 requests** answered, **3.5 million tokens**, 28 videos (32.8 minutes).
![Gemma requests answered by AMD Token Factory, by day](docs/charts/amd_usage.png) ![Gemma tokens of one finished minute, by version](docs/charts/e14_tokens.png)

---
<!-- slide: reliability -->
# It holds up
- Live attacks: 0 outputs reached a viewer: 8 cases, 20 tries each at two temperatures.
- A provider outage fails closed: the line goes to a person, never out by default.
- Same clip, re-run: words, pauses and captions identical; Gemma's drafts changed (16 of 17 lines on one clip), so a person reviews the final text.
- Tests: 215 of 215 unit and golden tests pass; browser tests with axe-core: player 28 of 28, review app and Studio 9 of 9.
- Other models on Token Factory writing the same attacks (E17): answers that reached a viewer, 0 for Qwen3.8-27B and 0 for MiniCPM-V-4.7-35B-A3B.

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
- **They buy:** every version per finished minute, below today's AI-description list prices, reviewed by their own staff in our app; or a yearly licence to run it on their own servers.
- **Next:** broadcasters and streaming platforms in the EU and India.
- **The difference:** every audience and language from one analysis, checks that catch meaning changes, and a server that refuses to publish unreviewed lines.

---
<!-- slide: honest -->
# What didn't work, and what's next
- **E1 did not work on our test set:** the W3C videos have 6 usable pauses in 9.3 minutes, so only 6 standard lines were planned and the arms came out equal.
- Gemma never failed 6 of our 8 attack cases, so those checks were not exercised live.
- Translation, one of two scores: the specialist model beat Gemma on chrF++ for Hindi (58.8 against 53.8), French (68.0 against 64.1) and Portuguese (70.0 against 67.4).
- Hindi speech recognition is weak: 32.4% word error rate.
- Token Factory dropped requests for long stretches; everything fails closed, but it slows the work.
- Not yet: a blind reviewer, native-speaker checks, MI300X numbers.

Prior work: AudioSight, ViddyScribe, AutoAD-Zero. Code: github.com/Prashant-thakur77/AccessCast · Live: accesscast.vercel.app
