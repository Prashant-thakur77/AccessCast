<!-- slide: title -->
# AccessCast
## One video. Five ways to watch.
<pending: e1.headline>

Gemma 4 on AMD Instinct MI300X · AMD Developer Hackathon ACT III · Create a New Kind of Experience

---
<!-- slide: problem -->
# Most video says nothing to people who can't see it
- <pending: cited.gbd.blind> people are blind and <pending: cited.gbd.mod_severe> have moderate to severe vision loss.
- <pending: cited.who.hearing> people need rehabilitation for disabling hearing loss.
- <pending: cited.oecd.literacy> of adults read at or below the lowest literacy level.
- The largest free archive of described video holds about <pending: cited.market.youdescribe_hours> hours. YouTube received <pending: cited.market.youtube_uploads> hours a minute.

---
<!-- slide: law -->
# The law already asks for it
| Where | Rule | When |
|---|---|---|
| EU | European Accessibility Act | <pending: cited.law.eaa_date> |
| Italy | D.Lgs. 82/2022, fines <pending: cited.law.italy_fines> | in force |
| India | MIB accessibility guidelines for OTT | <pending: cited.law.india_mib> |
| US | ADA Title II web rule (WCAG 2.1 AA) | <pending: cited.law.ada_title2> |

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
# Result: lines that fit the pauses
<pending: e01.table>

Test set: 10 W3C videos never used for tuning. Measured by a script that imports none of our checks.

---
<!-- slide: more-results -->
# More results
<pending: results.more>

---
<!-- slide: amd -->
# On one AMD MI300X
<pending: amd.slide>

---
<!-- slide: reliability -->
# It holds up
<pending: reliability.slide>

---
<!-- slide: business -->
# Who pays, and what it costs
<pending: business.slide>

Our cost is GPU time plus a person's review time. List prices are labelled as list prices.

---
<!-- slide: honest -->
# What didn't work, and what's next
<pending: negative.slide>

Prior work: AudioSight, ViddyScribe, AutoAD-Zero. Code: github.com/Prashant-thakur77/AccessCast · Live: accesscast.vercel.app
